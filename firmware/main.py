# ESP32-C3 8 路继电器主程序
# 控制串口可选 uart0 或 usb_cdc

import machine
import sys
import _thread
import time

# 控制串口选择：'uart0' 或 'usb_cdc'
CONTROL_SERIAL = 'uart0'

# 控制串口底层 UART：ESP32-C3 的 UART0 外设已被固件 REPL/调试占用
# （直接开 machine.UART(0) 会报 ESP_ERR_INVALID_STATE），
# 故用 UART1 外设 + 引脚矩阵，把信号映射回 GPIO21(TX)/GPIO20(RX) 两个焊盘，
# 硬件接线保持不变（默认 uart0 模式控制串口即接这两根线）。
UART_ID = 1
UART_TX_PIN = 21
UART_RX_PIN = 20


def _make_io():
    # 根据控制串口模式返回 (read_byte, write_bytes)
    if CONTROL_SERIAL == 'usb_cdc':
        # REPL 转到 GPIO20/21 硬件串口，控制走 USB CDC（sys.stdin/stdout）
        try:
            import os
            os.dupterm(machine.UART(UART_ID, 9600,
                                    tx=machine.Pin(UART_TX_PIN),
                                    rx=machine.Pin(UART_RX_PIN)), 1)
        except Exception as e:
            print('[main] dupterm UART error:', e)
        try:
            import select
        except Exception:
            select = None

        def read_byte():
            try:
                if select is not None:
                    r, _, _ = select.select([sys.stdin], [], [], 0)
                    if not r:
                        return None
                return sys.stdin.read(1)
            except Exception:
                return None

        def write_bytes(b):
            try:
                buf = getattr(sys.stdout, 'buffer', None)
                if buf is not None:
                    buf.write(b)
                else:
                    sys.stdout.write(''.join(chr(c) for c in b))
            except Exception as e:
                print('[main] usb write error:', e)

        return read_byte, write_bytes
    else:
        # 默认 uart0：UART1 外设驱动 GPIO20/21 引脚作控制串口
        # timeout=0：read() 无数据立即返回 None，不阻塞主循环（HTTP 轮询不能被卡住）
        ctrl_uart = machine.UART(UART_ID, 9600,
                                 tx=machine.Pin(UART_TX_PIN),
                                 rx=machine.Pin(UART_RX_PIN),
                                 timeout=0)

        def read_byte():
            # 批量读取当前可用的全部字节（而非 read(1) 逐字节轮询），
            # 降低主循环轮询开销、显著提升串口吞吐与响应速度
            try:
                return ctrl_uart.read()
            except Exception:
                return None

        def write_bytes(b):
            try:
                ctrl_uart.write(b)
            except Exception as e:
                print('[main] uart write error:', e)

        return read_byte, write_bytes


def main():
    # 初始化继电器（GPIO）
    from relay import relays
    # 创建串口控制 handler
    import serial_control
    ctrl = serial_control.SerialControl(relays)

    # 选择控制串口 IO
    read_byte, write_bytes = _make_io()

    # 启动 WiFi 后台线程（仅做连接/保活，阻塞 connect 不占用主循环）
    import wifi_manager
    _thread.start_new_thread(wifi_manager.connect_loop, ())

    # HTTP 服务：并入主循环 select 轮询（单核上子线程阻塞 accept 不可靠）
    import web_server
    web_server.poll_server()

    # 主循环：轮询 HTTP 连接 + 读取控制串口字节并分派
    while True:
        web_server.poll_server()
        b = read_byte()
        if b is not None and len(b) > 0:
            for byte in b:
                reply = ctrl.handle_byte(byte)
                if reply:
                    write_bytes(reply)
                    if reply == b"WIFI SAVED, REBOOTING\n":
                        # 等回包发出再重启
                        time.sleep(0.1)
                        machine.reset()
        else:
            time.sleep(0.002)


main()
