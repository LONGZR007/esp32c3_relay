# 串口控制状态机模块
# 兼容二进制帧协议与 ASCII 配置命令

import serial_proto
import config


class SerialControl:
    def __init__(self, relays_inst):
        # 保存继电器单例，初始化两个独立缓冲区
        self.relays_inst = relays_inst
        self.frame_buf = bytearray()
        self.ascii_buf = bytearray()

    def handle_byte(self, b):
        # 二进制帧优先：frame_buf 已有数据，或新帧以 HEADER 开头且未在 ASCII 模式
        if len(self.frame_buf) > 0 or (len(self.ascii_buf) == 0 and b == serial_proto.HEADER):
            return self._feed_binary(b)
        # ASCII 路径
        return self._feed_ascii(b)

    def _feed_binary(self, b):
        # 累积二进制帧，满 4 字节解析
        self.frame_buf.append(b)
        if len(self.frame_buf) < 4:
            return None
        try:
            result = serial_proto.parse(self.frame_buf)
        except Exception as e:
            print('[serial] parse error:', e)
            self.frame_buf = bytearray()
            return None
        # 无论成功失败都清空帧缓冲
        self.frame_buf = bytearray()
        if result is None:
            return None
        addr, func = result
        # 本设备仅 8 路，addr 1-8 有效，其余丢弃
        if addr < 1 or addr > 8:
            return None
        return self._dispatch(addr, func)

    def _dispatch(self, addr, func):
        # 按功能码分派
        try:
            if func == serial_proto.FUNC_OFF:
                self.relays_inst.set(addr, 0)
                return None
            elif func == serial_proto.FUNC_ON:
                self.relays_inst.set(addr, 1)
                return None
            elif func == serial_proto.FUNC_OFF_R:
                self.relays_inst.set(addr, 0)
                return serial_proto.build_state(addr, self.relays_inst.get(addr))
            elif func == serial_proto.FUNC_ON_R:
                self.relays_inst.set(addr, 1)
                return serial_proto.build_state(addr, self.relays_inst.get(addr))
            elif func == serial_proto.FUNC_TOGGLE:
                cur = self.relays_inst.get(addr)
                self.relays_inst.set(addr, 1 - cur)
                return serial_proto.build_state(addr, self.relays_inst.get(addr))
            elif func == serial_proto.FUNC_QUERY:
                return serial_proto.build_state(addr, self.relays_inst.get(addr))
            else:
                # 未知功能码，丢弃
                return None
        except Exception as e:
            print('[serial] dispatch error:', e)
            return None

    def _feed_ascii(self, b):
        # CR 忽略，LF 触发行解析
        if b == 0x0D:
            return None
        if b == 0x0A:
            reply = self._process_ascii_line()
            self.ascii_buf = bytearray()
            return reply
        if 0x20 <= b <= 0x7E:
            self.ascii_buf.append(b)
            return None
        # 非可打印 ASCII，丢弃
        return None

    def _process_ascii_line(self):
        # 解析 wifi:<ssid>,pwd:<password> 命令
        if len(self.ascii_buf) == 0:
            return None
        try:
            line = bytes(self.ascii_buf).decode('utf-8', 'ignore').strip()
        except Exception:
            return None
        if not line:
            return None
        if not line.startswith('wifi:'):
            # 非 wifi 命令，丢弃
            return None
        rest = line[5:]
        if ',pwd:' in rest:
            idx = rest.find(',pwd:')
            ssid = rest[:idx]
            pwd = rest[idx + 5:]
            config.save_wifi(ssid, pwd)
            return b"WIFI SAVED, REBOOTING\n"
        else:
            return b"ERROR: bad format, expected wifi:<ssid>,pwd:<password>\n"


def make_handler(relays_inst):
    # 工厂函数，返回 SerialControl 实例
    return SerialControl(relays_inst)
