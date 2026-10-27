"""RCC — 复位与时钟控制（0x40021000）。寄存器后备存储 + ready 位即时置位。"""
from __future__ import annotations
from . import Peripheral


class Rcc(Peripheral):
    name = "RCC"
    base = 0x40021000
    size = 0x20
    RESET_VALUES = {
        0x00: 0x00000083,   # CR: HSION|HSIRDY
        0x04: 0x00000000,   # CFGR
        0x08: 0x00000000,   # CIR
        0x0C: 0x00000000,   # APB2RSTR
        0x10: 0x00000000,   # APB1RSTR
        0x14: 0x00000000,   # AHBENR
        0x18: 0x00000000,   # APB2ENR
        0x1C: 0x00000000,   # APB1ENR
        0x20: 0x00000018,   # BDCR
        0x24: 0x03000000,   # CSR
    }

    def __init__(self):
        super().__init__()
        self.on_enable_change = None       # 回调：board 重同步外设时钟门

    def reset(self):
        super().reset()
        self.regs.update(self.RESET_VALUES)

    def write(self, off, size, value):
        super().write(off, size, value)
        if off == 0x00:                    # CR：ready 位即时置起
            cr = self.regs[0x00]
            if cr & 0x00010000:            # HSEON
                cr |= 1 << 17
            if cr & 0x01000000:            # PLLON
                cr |= 1 << 25
            cr |= 1 << 1                   # HSIRDY
            self.regs[0x00] = cr
        if off in (0x18, 0x1C, 0x14) and self.on_enable_change:
            self.on_enable_change()
