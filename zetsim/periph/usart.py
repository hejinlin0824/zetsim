"""USART1/2/3、UART4/5 — SR/DR/BRR/CR1-3/GTPR。"""
from __future__ import annotations
from . import Peripheral
from .sysctrl import IRQ

# 实例参数: (基址, IRQ名, 用 APB2(否则 APB1))
_INSTANCES = {
    1: (0x40013800, "USART1", True),
    2: (0x40004400, "USART2", False),
    3: (0x40004800, "USART3", False),
    4: (0x40004C00, "UART4", False),
    5: (0x40005000, "UART5", False),
}


class Usart(Peripheral):
    size = 0x1C

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        base, irq_name, apb2 = _INSTANCES[index]
        self.base = base
        self.name = f"USART{index}" if index <= 3 else f"UART{index}"
        self.irq_name = irq_name
        self.clock_gate_apb2 = apb2
        self.clock_gate = (0x18, {1: 14, 2: 17, 3: 18, 4: 19, 5: 20}[index])
        self.tx_bytes: bytearray = bytearray()
        self._rx_dr = 0
        self._tc_at_ns = 0                  # TC 置位时刻
        self._dma = None                    # 注入 DMA 模型（M5）

    def reset(self):
        super().reset()
        self.regs[0x00] = 0x00C0            # TXE|TC
        self.tx_bytes = bytearray()
        self._rx_dr = 0
        self._tc_at_ns = 0

    # ---------------- 波特率 ----------------
    def baud_hz(self) -> float:
        brr = self.regs.get(0x08, 0)
        mant, frac = brr >> 4, brr & 0xF
        div = mant + frac / 16
        if div == 0:
            return 1.0
        pclk = self.clock.pclk2_hz if self.clock_gate_apb2 else self.clock.pclk1_hz
        return pclk / div

    def _bit_ns(self) -> float:
        return 1 / self.baud_hz() * 1e9

    # ---------------- 寄存器行为 ----------------
    def read(self, off, size):
        if off == 0x00:                      # SR：动态位
            sr = self.regs.get(0x00, 0x00C0)
            if self._tc_at_ns and self.now_ns >= self._tc_at_ns:
                sr |= 1 << 6                 # TC
                self.regs[0x00] = sr
            return sr
        if off == 0x04:                      # DR：读清 RXNE
            cr1 = self.regs.get(0x0C, 0)
            val = self._rx_dr
            if cr1 & (1 << 2):               # RE
                self.regs[0x00] = self.regs.get(0x00, 0) & ~(1 << 5)
            return val & 0xFF
        return super().read(off, size)

    def write(self, off, size, value):
        if off == 0x04:                      # DR：发送
            cr1 = self.regs.get(0x0C, 0)
            if cr1 & (1 << 3):               # TE
                self.tx_bytes.append(value & 0xFF)
                self.evt(f"{self.name.lower()}.tx", value & 0xFF)
                self._tc_at_ns = self.now_ns + 10 * self._bit_ns()
                self.regs[0x00] &= ~(1 << 6)
            return
        if off == 0x00:                      # SR：TC 写 0 清
            self.regs[0x00] = self.regs.get(0x00, 0) & ~(value & (1 << 6))
            return
        super().write(off, size, value)
        if off == 0x08:                      # BRR
            pass

    # ---------------- 外部注入 ----------------
    def inject_rx(self, byte: int):
        cr1 = self.regs.get(0x0C, 0)
        if not (cr1 & (1 << 2)):             # RE 关闭则丢弃
            return
        sr = self.regs.get(0x00, 0)
        if sr & (1 << 5):                    # RXNE 未读 -> 简化为覆盖（不模拟 ORE 队列）
            self.regs[0x00] |= 1 << 3        # ORE
        self._rx_dr = byte & 0xFF
        self.regs[0x00] |= 1 << 5            # RXNE
        self.evt(f"{self.name.lower()}.rx", byte & 0xFF)
        if cr1 & (1 << 5):                   # RXNEIE
            self.irq(IRQ[self.irq_name])

    def step_to(self, now_ns):
        super().step_to(now_ns)

    def next_event_ns(self):
        return None
