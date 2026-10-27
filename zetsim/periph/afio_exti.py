"""AFIO（EXTI 线路映射）+ EXTI（0x40010400）。"""
from __future__ import annotations
from . import Peripheral
from .sysctrl import IRQ


class Afio(Peripheral):
    name = "AFIO"
    base = 0x40010000
    size = 0x18

    def exti_port(self, line: int) -> int:
        """EXTI 线路映射到的端口索引（0=PA..4=PE），4bit/line。"""
        reg = self.regs.get(0x08 + (line // 4) * 4, 0)
        return (reg >> ((line % 4) * 4)) & 0xF


class Exti(Peripheral):
    name = "EXTI"
    base = 0x40010400
    size = 0x18

    def __init__(self):
        super().__init__()
        self.afio: Afio = None

    def _irq_for(self, line: int) -> int:
        if line <= 4:
            name = f"EXTI{line}"
        elif line <= 9:
            name = "EXTI9_5"
        else:
            name = "EXTI15_10"
        return IRQ[name]

    def write(self, off, size, value):
        if off == 0x10:                              # SWIER
            for line in range(16):
                if (value >> line) & 1:
                    self._trigger(line)
            return
        if off == 0x14:                              # PR 写 1 清
            self.regs[0x14] &= ~value & 0xFFFF
            return
        super().write(off, size, value)

    def read(self, off, size):
        if off == 0x14:
            return self.regs.get(0x14, 0) & 0xFFFF
        return super().read(off, size)

    def _trigger(self, line: int):
        self.regs[0x14] = self.regs.get(0x14, 0) | (1 << line)
        if (self.regs.get(0x00, 0) >> line) & 1:      # IMR
            self.irq(self._irq_for(line))

    def on_net_edge(self, port_idx: int, pin: int, old, new):
        """由 board 在网络电平变化时调用。"""
        if old == new:
            return
        if self.afio.exti_port(pin) != port_idx:
            return
        line = pin
        imr = self.regs.get(0x00, 0)
        if not (imr >> line) & 1:
            return
        rising = (new in (1,)) and old != 1
        falling = (new in (0,)) and old != 0
        rtsr = (self.regs.get(0x08, 0) >> line) & 1
        ftsr = (self.regs.get(0x0C, 0) >> line) & 1
        if (rising and rtsr) or (falling and ftsr):
            self._trigger(line)
