# 串口后端：通过 pyserial 直连 ESP32-C3，使用 4 字节帧协议
import time
import serial
from base_client import BaseClient

# 帧头固定值
HEADER = 0xA0


class SerialClient(BaseClient):
    def __init__(self, port: str, baudrate: int = 115200):
        # 保存串口配置，初始化句柄并尝试打开
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.open()

    def open(self):
        # 打开串口，异常时打印并置空句柄
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        except Exception as e:
            print("[serial] open error:", e)
            self.ser = None

    def close(self):
        # 关闭句柄并置空
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def reopen(self):
        # 关闭旧句柄，重新基于 self.port / self.baudrate 配置调用 open()
        # 异常重开必须重载配置（即使 self 上配置不变，也保证从配置重新加载的语义）
        self.close()
        port = self.port
        baudrate = self.baudrate
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
        except serial.SerialException as e:
            self.close()
            raise RuntimeError("serial write failed")

    def _read_reply(self, expected_addr):
        # 读 4 字节回包，校验帧头/校验和/地址，成功返回 (addr, state)
        try:
            data = self.ser.read(4)
        except serial.SerialException as e:
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

    def set_relay(self, channel: int, state: int, with_reply: bool = False) -> dict:
        # 设置单路继电器。channel 1-8，state 0/1。
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        if state not in (0, 1):
            raise ValueError("state must be 0 or 1")
        try:
            self._ensure_open()
            if with_reply:
                func = 0x03 if state == 1 else 0x02
                self._send_frame(channel, func)
                _, state = self._read_reply(channel)
            else:
                func = 0x01 if state == 1 else 0x00
                self._send_frame(channel, func)
            return {"ok": True, "channel": channel, "state": state}
        except RuntimeError as e:
            return {"ok": False, "channel": channel, "state": state, "error": str(e)}

    def get_relay(self, channel: int) -> dict:
        # 查询单路继电器状态。channel 1-8。
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        try:
            self._ensure_open()
            self._send_frame(channel, 0x05)
            _, state = self._read_reply(channel)
            return {"channel": channel, "state": state}
        except RuntimeError as e:
            return {"channel": channel, "state": -1, "error": str(e)}

    def toggle_relay(self, channel: int) -> dict:
        # 翻转单路继电器。channel 1-8。
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        try:
            self._ensure_open()
            self._send_frame(channel, 0x04)
            _, state = self._read_reply(channel)
            return {"channel": channel, "state": state}
        except RuntimeError as e:
            return {"channel": channel, "state": -1, "error": str(e)}

    def set_all_relays(self, state: int) -> dict:
        # 批量设置全部 8 路。state 0/1。
        if state not in (0, 1):
            raise ValueError("state must be 0 or 1")
        for ch in range(1, 9):
            r = self.set_relay(ch, state, with_reply=False)
            if not r.get("ok"):
                return {"ok": False, "state": state, "error": r.get("error", "unknown")}
        return {"ok": True, "state": state}

    def get_all_relays(self) -> list:
        # 查询全部 8 路状态。
        return [self.get_relay(ch) for ch in range(1, 9)]

    def set_wifi(self, ssid: str, password: str) -> str:
        # 通过 ASCII 命令配置 WiFi，设备收到后会重启。
        try:
            self._ensure_open()
            cmd = "wifi:{ssid},pwd:{password}\n".format(ssid=ssid, password=password).encode("utf-8")
            try:
                self.ser.write(cmd)
            except serial.SerialException as e:
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
