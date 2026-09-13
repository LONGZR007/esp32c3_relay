# 8 路继电器控制模块
# 通道 1-8 -> GPIO0-7
# （GPIO8 已改作 WiFi 指示灯，见 wifi_manager.py）
#
# 硬件：继电器低电平吸合（GPIO 输出 0 = 吸合，输出 1 = 断开）
# 对外接口语义不变：state=1 表示吸合，state=0 表示断开
# 内部做电平翻转：state=1 -> pin=0，state=0 -> pin=1

import machine

# 通道 -> GPIO 引脚映射
PIN_MAP = [0, 1, 2, 3, 4, 5, 6, 7]  # 通道1-8 = GPIO0-7


class Relays:
    def __init__(self):
        # 初始化各通道为输出，默认断开（state=0 -> pin 高电平）
        self.pins = []
        for pin in PIN_MAP:
            self.pins.append(machine.Pin(pin, machine.Pin.OUT, value=1))

    def _to_level(self, state):
        # 对外 state(1=吸合,0=断开) -> 物理电平(0=吸合,1=断开)
        return 0 if state else 1

    def _to_state(self, level):
        # 物理电平 -> 对外 state
        return 1 if level == 0 else 0

    def set(self, ch, state):
        # ch 范围 1-8，state 非 0/1 抛 ValueError
        if ch < 1 or ch > 8:
            raise ValueError('channel out of range: {}'.format(ch))
        if state != 0 and state != 1:
            raise ValueError('bad state: {}'.format(state))
        self.pins[ch - 1].value(self._to_level(state))

    def get(self, ch):
        # ch 范围 1-8，返回 0/1（对外语义：1=吸合，0=断开）
        if ch < 1 or ch > 8:
            raise ValueError('channel out of range: {}'.format(ch))
        return self._to_state(self.pins[ch - 1].value())

    def set_all(self, state):
        # state 非 0/1 抛 ValueError，所有通道同状态
        if state != 0 and state != 1:
            raise ValueError('bad state: {}'.format(state))
        v = self._to_level(state)
        for p in self.pins:
            p.value(v)

    def get_all(self):
        # 返回 [ch1..ch8] 状态列表（对外语义：1=吸合，0=断开）
        return [self._to_state(p.value()) for p in self.pins]


# 模块级单例
relays = Relays()
