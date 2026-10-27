"""DAC — 双通道 12 位电压输出（PA4=CH1, PA5=CH2）。"""
from __future__ import annotations
from . import Peripheral

_CH_PINS = {1: (0, 4), 2: (0, 5)}


class Dac(Peripheral):
    name = "DAC"
    base = 0x40007400
    size = 0x40
    clock_gate = (0x1C, 29)
    clock_gate_apb2 = False

    def __init__(self):
        super().__init__()
        self._out = [None, None]

    def write(self, off, size, value):
        super().write(off, size, value)
        # DHR12Rx 写 -> 立即更新 DOR（简化：无建立时间）
        for ch, dhr_off, dor_off in ((1, 0x08, 0x2C), (2, 0x14, 0x30)):
            if off == dhr_off:
                v = value & 0xFFF
                self.regs[dor_off] = v
                volts = v / 4095 * 3.3
                port, pin = _CH_PINS[ch]
                # 使能位：CR EN1/EN2
                en = self.regs.get(0x00, 0) & (1 << (ch - 1))
                if self.board:
                    self.board.set_pin_analog(port, pin, volts if en else None)

    def read(self, off, size):
        return super().read(off, size)
