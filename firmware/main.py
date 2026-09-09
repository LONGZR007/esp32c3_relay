# ESP32-C3 8 路继电器主程序
# 控制串口可选 uart0 或 usb_cdc

import machine
import sys
import _thread
import time

# 控制串口选择：'uart0' 或 'usb_cdc'
CONTROL_SERIAL = 'uart0'


def _make_io():
    # 根据控制串口模式返回 (read_byte, write_bytes)
    if CONTROL_SERIAL == 'usb_cdc':
        # REPL 转到 UART0，控制走 USB CDC（sys.stdin/stdout）
        try:
            import os
            os.dupterm(machine.UART(0, 115200), 1)
        except Exception as e:
            print('[main] dupterm UART0 error:', e)
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
        # 默认 uart0 作控制串口
        ctrl_uart = machine.UART(0, 115200)

        def read_byte():
            try:
                return ctrl_uart.read(1)
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

    # 启动 WiFi 后台线程
    import wifi_manager
    _thread.start_new_thread(wifi_manager.connect_loop, ())

    # 启动 HTTP 后台线程
    import web_server
    web_server.start_server_thread()

    # 主循环：读取控制串口字节并分派
    while True:
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
            time.sleep(0.01)


main()
