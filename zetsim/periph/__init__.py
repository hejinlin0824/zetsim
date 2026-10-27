"""外设模型基类。

约定：
- regs: dict[字偏移->int]，作为默认寄存器后备存储（写读自动回显）
- read/write 钩子按 RM0008 实现行为（读副作用、写触发）
- step_to(now_ns)/next_event_ns 支撑事件驱动的仿真循环
"""
from __future__ import annotations


class Peripheral:
    name = "?"
    base = 0
    size = 0x400
    # RCC 使能位：(寄存器偏移, bit) —— None 表示始终有钟
    clock_gate = None
    clock_gate_apb2 = True

    def __init__(self):
        self.regs: dict[int, int] = {}
        self.board = None              # 注入：访问引脚/事件
        self.clock = None              # 注入：ClockTree
        self.now_ns = 0
        self._clock_enabled = True

    # ---- 生命周期 ----
    def reset(self):
        self.regs.clear()
        self.now_ns = 0

    def sync_clock_gate(self):
        """RCC 使能位变化后由 RCC 调用 / 引擎周期调用。"""
        if self.clock_gate is None or self.board is None:
            return
        reg, bit = self.clock_gate
        en = (self.board.rcc.regs.get(reg, 0) >> bit) & 1
        self._clock_enabled = bool(en)

    # ---- 总线接口 ----
    def read(self, off: int, size: int) -> int:
        word_off = off & ~3
        v = self.regs.get(word_off, 0)
        shift = (off & 3) * 8
        return (v >> shift) & ((1 << (size * 8)) - 1)

    def write(self, off: int, size: int, value: int):
        word_off = off & ~3
        shift = (off & 3) * 8
        mask = ((1 << (size * 8)) - 1) << shift
        cur = self.regs.get(word_off, 0)
        self.regs[word_off] = (cur & ~mask) | ((value << shift) & mask)

    # ---- 时间推进 ----
    def step_to(self, now_ns: int):
        self.now_ns = now_ns

    def next_event_ns(self) -> int | None:
        return None

    # ---- 工具 ----
    def irq(self, irq_no: int, on: bool = True):
        """irq_no 为外部 IRQ 号（0-59，对应 IRQ 表），内部转异常号 16+n。"""
        self.board.sysctrl.set_pending(16 + irq_no, on)

    def evt(self, topic: str, data=None):
        if self.board:
            self.board.events.publish(self.now_ns, topic, data)


def reg_bits(v: int, hi: int, lo: int) -> int:
    return (v >> lo) & ((1 << (hi - lo + 1)) - 1)
