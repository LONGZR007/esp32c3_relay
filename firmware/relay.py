# 8 路继电器控制模块
# GPIO1-8 对应通道 1-8

import machine


class Relays:
    def __init__(self):
        # 初始化 GPIO1..8 为输出，默认低电平
        self.pins = []
        for i in range(1, 9):
            self.pins.append(machine.Pin(i, machine.Pin.OUT, value=0))

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
