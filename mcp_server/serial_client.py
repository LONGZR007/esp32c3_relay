# 串口后端：通过 pyserial 直连 ESP32-C3，使用 4 字节帧协议
# 对外暴露 turn_on_ack / turn_off_ack / toggle / query（带应答），返回继电器吸合状态 0/1
import time
import serial
from base_client import BaseClient

# 帧头固定值（与 firmware/serial_proto.py 一致）
HEADER = 0xA0


class SerialClient(BaseClient):
    def __init__(self, port: str, baudrate: int = 9600):
        # 保存串口配置，句柄惰性打开（首次操作时才 open）
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self._need_reload = False
        # 上次打开失败后，再次打开前需要重新读 config（由上层 RelayService 在重载后调 set_port 更新）
        self.open()

    def set_port(self, port: str, baudrate: int) -> None:
        """更新串口配置（config 重载后调用），下次 open 使用新值。"""
        self.port = port
        self.baudrate = baudrate

    def open(self):
        # 打开串口，异常时打印并置空句柄，标记下次需重载配置
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        except Exception as e:
            print("[serial] open error:", e)
            self.ser = None
            self._need_reload = True

    def close(self):
        # 关闭句柄并置空
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def release_serial(self) -> dict:
        """释放串口，下次操作会惰性重开（且若曾打开失败会先重载 config）。"""
        was_open = self.ser is not None
        self.close()
        return {"released": was_open, "mode": "serial"}

    def reopen(self):
        # 关闭旧句柄，重新基于 self.port / self.baudrate 配置调用 open()
        # 异常重开必须重载配置（即使 self 上配置不变，也保证从配置重新加载的语义）
        self.close()
        self.open()

    def _ensure_open(self):
        # 句柄无效则重开，仍失败则抛异常
        if self.ser is None or not self.ser.is_open:
            self.reopen()
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("serial not open")

    def _send_frame(self, addr, func):
        # 构造 4 字节帧 [HEADER, addr, func, checksum] 并发送
        frame = bytes([HEADER, addr, func, (HEADER + addr + func) & 0xFF])
        try:
            self.ser.write(frame)
        except serial.SerialException:
            self.close()
            raise RuntimeError("serial write failed")

    def _read_reply(self, expected_addr):
        # 读 4 字节回包，校验帧头/校验和/地址，成功返回 (addr, state)
        try:
            data = self.ser.read(4)
        except serial.SerialException:
            self.close()
            raise RuntimeError("serial read failed")
        if len(data) < 4:
            self.close()
            raise RuntimeError("serial read timeout")
        if data[0] != HEADER:
            raise RuntimeError("bad reply")
        addr = data[1]
        state = data[2]
        chk = data[3]
        if (data[0] + addr + state) & 0xFF != chk:
            raise RuntimeError("bad reply")
        if addr != expected_addr:
            raise RuntimeError("bad reply")
        return (addr, state)

    def _ack_op(self, channel: int, func: int) -> int:
        # 通用：发送带应答功能码，读回包返回实测吸合状态 0/1
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        self._ensure_open()
        self._send_frame(channel, func)
        _, state = self._read_reply(channel)
        return state

    def turn_on_ack(self, channel: int) -> int:
        # 继电器吸合并应答（功能码 0x03）
        return self._ack_op(channel, 0x03)

    def turn_off_ack(self, channel: int) -> int:
        # 继电器断开并应答（功能码 0x02）
        return self._ack_op(channel, 0x02)

    def toggle(self, channel: int) -> int:
        # 翻转继电器并应答（功能码 0x04），返回翻转后状态
        return self._ack_op(channel, 0x04)

    def query(self, channel: int) -> int:
        # 查询继电器状态（功能码 0x05）
        return self._ack_op(channel, 0x05)

    def set_wifi(self, ssid: str, password: str) -> str:
        # 通过 ASCII 命令配置 WiFi，设备收到后会重启
        try:
            self._ensure_open()
            cmd = "wifi:{ssid},pwd:{password}\n".format(ssid=ssid, password=password).encode("utf-8")
            try:
                self.ser.write(cmd)
            except serial.SerialException:
                self.close()
                raise RuntimeError("serial write failed")
            # 设备收到 wifi 命令会 reset，读回显时端口可能已断开
            time.sleep(0.3)
            try:
                data = self.ser.read(64)
            except Exception:
                self.close()
                return "sent (device may reboot)"
            if data:
                return data.decode("utf-8", "ignore").rstrip("\r\n")
            return "sent (device may reboot)"
        except Exception as e:
            return "ERROR: " + str(e)
