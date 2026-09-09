# 串口通信协议模块
# 帧格式: [HEADER, ADDR, FUNC, CHECKSUM]
# CHECKSUM = (HEADER + ADDR + FUNC) & 0xFF

HEADER = 0xA0

# 功能码
FUNC_OFF = 0x00       # 关闭（无回包）
FUNC_ON = 0x01        # 打开（无回包）
FUNC_OFF_R = 0x02     # 关闭并回读
FUNC_ON_R = 0x03      # 打开并回读
FUNC_TOGGLE = 0x04    # 翻转并回读
FUNC_QUERY = 0x05     # 查询


def parse(frame):
    # 解析 4 字节帧，校验失败返回 None，成功返回 (addr, func)
    if not isinstance(frame, (bytes, bytearray)):
        return None
    if len(frame) != 4:
        return None
    if frame[0] != HEADER:
        return None
    if (frame[0] + frame[1] + frame[2]) & 0xFF != frame[3]:
        return None
    addr = frame[1]
    # addr 必须 0x01-0xFE，0x00/0xFF 非法
    if addr < 0x01 or addr > 0xFE:
        return None
    return (addr, frame[2])


def build_state(addr, state):
    # 构造 4 字节回包 [HEADER, addr, state, checksum]
    chk = (HEADER + addr + state) & 0xFF
    return bytes([HEADER, addr, state, chk])
