# 8 路继电器控制模块
# 通道 1-8 -> GPIO0-7
# （GPIO8 已改作 WiFi 指示灯，见 wifi_manager.py）

import machine

# 通道 -> GPIO 引脚映射
# PIN_MAP = [0, 1, 2, 3, 4, 5, 6, 7]  # 目标方案（通道1-8 = GPIO0-7）
PIN_MAP = [1, 2, 3, 4, 5, 6, 7, 9]  # 对比实验：旧映射，验证 wifi 是否受 GPIO0 影响


class Relays:
    def __init__(self):
        # 初始化各通道为输出，默认低电平
        self.pins = []
        for pin in PIN_MAP:
            self.pins.append(machine.Pin(pin, machine.Pin.OUT, value=0))

    def set(self, ch, state):
        # ch 范围 1-8，state 非 0/1 抛 ValueError
        if ch < 1 or ch > 8:
            raise ValueError('channel out of range: {}'.format(ch))
        if state != 0 and state != 1:
            raise ValueError('bad state: {}'.format(state))
        self.pins[ch - 1].value(1 if state else 0)

    def get(self, ch):
        # ch 范围 1-8，返回 0/1
        if ch < 1 or ch > 8:
            raise ValueError('channel out of range: {}'.format(ch))
        return self.pins[ch - 1].value()

    def set_all(self, state):
        # state 非 0/1 抛 ValueError，所有通道同状态
        if state != 0 and state != 1:
            raise ValueError('bad state: {}'.format(state))
        v = 1 if state else 0
        for p in self.pins:
            p.value(v)

    def get_all(self):
        # 返回 [ch1..ch8] 状态列表
        return [p.value() for p in self.pins]


# 模块级单例
relays = Relays()
