"""SPI1/2/3 — 主模式收发（TX 即时、RX 回显/器件应答）。"""
from __future__ import annotations
from . import Peripheral
from .sysctrl import IRQ

_INST = {1: (0x40013000, 12, True, "SPI1"), 2: (0x40003800, 14, False, "SPI2"),
         3: (0x40003C00, 15, False, "SPI3")}


class Spi(Peripheral):
    size = 0x10

    def __init__(self, index: int):
        super().__init__()
        base, en_bit, apb2, name = _INST[index]
        self.base = base
        self.name = name
        self.irq_name = name
        reg = 0x18 if apb2 else 0x1C
        self.clock_gate = (reg, en_bit)
        self.clock_gate_apb2 = apb2
        self._rx_dr = 0
        self._rx_ready_at = None
        self._device = None                 # 可挂 SPI 器件（MISO 来源）

    def reset(self):
        super().reset()
        self.regs[0x08] = 0x0002            # SR: TXE
        self._rx_dr = 0
        self._rx_ready_at = None

    def _bit_ns(self):
        br = (self.regs.get(0x00, 0) >> 3) & 7
        div = 2 ** (br + 1)
        pclk = self.clock.pclk2_hz if self.clock_gate_apb2 else self.clock.pclk1_hz
        return div / pclk * 1e9

    def write(self, off, size, value):
        if off == 0x0C:                     # DR：主发送
            cr1 = self.regs.get(0x00, 0)
            if (cr1 & (1 << 6)) and (cr1 & (1 << 2)):      # SPE|MSTR
                self.evt(f"{self.name.lower()}.tx", value & 0xFF)
                self._rx_dr = (self._device.reply(value & 0xFF) if self._device
                               else value & 0xFF)          # 默认回环
                self._rx_ready_at = self.now_ns + 8 * self._bit_ns()
            return
        super().write(off, size, value)

    def read(self, off, size):
        if off == 0x08:                     # SR：RXNE 到点置位
            sr = self.regs.get(0x08, 2)
            if self._rx_ready_at and self.now_ns >= self._rx_ready_at:
                sr |= 1
                self.regs[0x08] = sr
            return sr
        if off == 0x0C:                     # DR：读清 RXNE
            sr = self.regs.get(0x08, 2)
            self.regs[0x08] = sr & ~1
            return self._rx_dr
        return super().read(off, size)

    def step_to(self, now_ns):
        self.now_ns = now_ns
        if self._rx_ready_at and now_ns >= self._rx_ready_at:
            self.regs[0x08] = self.regs.get(0x08, 2) | 1 | 2      # RXNE|TXE
            self.evt(f"{self.name.lower()}.rx", self._rx_dr)
            self._rx_ready_at = None

    def next_event_ns(self):
        return self._rx_ready_at
