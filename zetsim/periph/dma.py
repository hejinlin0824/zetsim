"""DMA1/2 — 多通道直接存储器搬运（P2M/M2P/P2P、MINC/PINC、CIRC、TC 中断）。

传输即时完成（burst 语义），时间粒度=请求时刻。ADC/USART 请求源已接。
"""
from __future__ import annotations
from . import Peripheral
from .sysctrl import IRQ


class DmaChannel:
    def __init__(self, dma, ch_idx):
        self.dma = dma
        self.ch = ch_idx                    # 0-based
        self.regs: dict[int, int] = {}
        self.cmar_base = 0                  # CIRC 重装基准

    @property
    def off(self):
        return 8 + 20 * self.ch

    def _ccr(self): return self.regs.get(0, 0)
    def _dir_to_mem(self): return not (self._ccr() & (1 << 4))

    def transfer_one(self, read_periph=None, write_periph=None):
        ccr = self._ccr()
        if not (ccr & 1):                   # EN
            return
        psize = 1 << ((ccr >> 8) & 3)
        msize = 1 << ((ccr >> 10) & 3)
        cpar, cmar = self.regs.get(8, 0), self.regs.get(0xC, 0)
        ndtr = self.regs.get(4, 0)
        if ndtr == 0:
            return
        bus = self.dma.board.core.mem
        if self._dir_to_mem():              # 外设 -> 内存
            val = self.dma.bus.read(cpar, psize)
            self.dma.bus.write(cmar, msize, val)
        else:                               # 内存 -> 外设
            val = self.dma.bus.read(cmar, msize)
            self.dma.bus.write(cpar, psize, val)
        if ccr & (1 << 7):                  # MINC
            self.regs[0xC] = cmar + msize
        if ccr & (1 << 6):                  # PINC
            self.regs[8] = cpar + psize
        self.regs[4] = ndtr - 1
        if self.regs[4] == 0:
            isr = self.dma.regs.get(0, 0)
            self.dma.regs[0] = isr | (1 << (self.ch * 4 + 1))     # TCIF
            if ccr & 2 and self.dma.board:
                self.dma.irq(IRQ[f"DMA1_CH{self.ch + 1}"] if self.dma.index == 1
                             else IRQ[f"DMA2_CH{self.ch + 1}"])
            if ccr & (1 << 5):              # CIRC 重装
                self.regs[4] = self.regs.get(4) or 0
                self.regs[0xC] = self.cmar_base or cmar
                # 重新装载 CNDTR
                self.regs[4] = self._ndtr_reload

    _ndtr_reload = 0

    def set_cmar(self, v):
        self.regs[0xC] = v
        self.cmar_base = v


class Dma(Peripheral):
    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.base = 0x40020000 + 0x400 * (index - 1)
        self.name = f"DMA{index}"
        self.size = 0x400
        nch = 7 if index == 1 else 5
        self.channels = [DmaChannel(self, i) for i in range(nch)]
        self.bus = None                     # 注入 SystemBus
        # 请求源表：请求名 -> (通道索引, 外设)
        self.requests: dict[str, tuple[int, object]] = {}

    # ---- 请求接口（外设调用） ----
    def bind(self, name: str, ch_idx: int, periph):
        self.requests[name] = (ch_idx, periph)

    def request(self, periph, ch_idx: int):
        ch = self.channels[ch_idx]
        if ch._ccr() & 1:
            ch.transfer_one()

    # ---- 寄存器 ----
    def _ch_for(self, off):
        idx = (off - 8) // 20
        if 0 <= idx < len(self.channels):
            return self.channels[idx]
        return None

    def read(self, off, size):
        ch = self._ch_for(off)
        if ch:
            return ch.regs.get(off - ch.off, 0)
        if off == 0x00:                     # ISR
            return self.regs.get(0, 0)
        return super().read(off, size)

    def write(self, off, size, value):
        ch = self._ch_for(off)
        if ch:
            co = off - ch.off
            ch.regs[co] = value
            if co == 0x0C:
                ch.set_cmar(value)
            if co == 4:
                ch._ndtr_reload = value
            return
        if off == 0x04:                     # IFCR 写 1 清
            self.regs[0] &= ~value
            return
        super().write(off, size, value)
