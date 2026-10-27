"""TIM1-8 — 通用/高级定时器（向上计数、PWM 输出、更新中断）。

精确度策略：step_to 用解析法展开 (last, now] 内的所有溢出/比较事件，
边沿时间戳精确到滴答，PWM 频率/占空比与真机公式一致。
已知简化（docs/accuracy.md）：ARPE/CCR 预装载、重复计数器 RCR、输入捕获、
向下/中央对齐计数未建模。
"""
from __future__ import annotations
from . import Peripheral
from .sysctrl import IRQ

# TIM 实例: (基址, UP中断名, CC中断名(None=共用), APB2?)  基址经 SVD 交叉验证
_INST = {
    1: (0x40012C00, "TIM1_UP", "TIM1_CC", True),
    2: (0x40000000, "TIM2", None, False),
    3: (0x40000400, "TIM3", None, False),
    4: (0x40000800, "TIM4", None, False),
    5: (0x40000C00, "TIM5", None, False),
    6: (0x40001000, "TIM6", None, False),
    7: (0x40001400, "TIM7", None, False),
    8: (0x40013400, "TIM8_UP", "TIM8_CC", True),
}

# 默认引脚映射（无 remap）：定时器通道 -> (端口索引, 引脚)
_AF_PINS = {
    (1, 1): (0, 8), (1, 2): (0, 9), (1, 3): (0, 10), (1, 4): (0, 11),
    (2, 1): (0, 0), (2, 2): (0, 1), (2, 3): (0, 2), (2, 4): (0, 3),
    (3, 1): (0, 6), (3, 2): (0, 7), (3, 3): (1, 0), (3, 4): (1, 1),
    (4, 1): (1, 6), (4, 2): (1, 7), (4, 3): (1, 8), (4, 4): (1, 9),
}

# RCC 使能位: TIM1 APB2 bit11, TIM8 APB2 bit13, TIM2-4 APB1 bit0-2, TIM5 APB1 bit3, TIM6/7 bit4/5
_GATE = {1: ((0x18, 11), True), 2: ((0x1C, 0), False), 3: ((0x1C, 1), False),
         4: ((0x1C, 2), False), 5: ((0x1C, 3), False), 6: ((0x1C, 4), False),
         7: ((0x1C, 5), False), 8: ((0x18, 13), True)}


class Timer(Peripheral):
    size = 0x50                # DMAR 在 0x4C

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        base, up_irq, cc_irq, apb2 = _INST[index]
        self.base = base
        self.name = f"TIM{index}"
        self.up_irq, self.cc_irq, self.apb2 = up_irq, cc_irq, apb2
        (reg, bit), is2 = _GATE[index]
        self.clock_gate = (reg, bit)
        self.clock_gate_apb2 = is2
        self.advanced = index in (1, 8)
        self.basic = index in (6, 7)          # 基本定时器：无通道
        self._cnt = 0.0
        self._last_ns = 0
        self._out = [0, 0, 0, 0]              # 各通道当前输出
        self._dma = None

    def reset(self):
        super().reset()
        self._cnt = 0.0
        self._last_ns = 0
        self._out = [0, 0, 0, 0]

    # ---------- 寄存器 ----------
    def read(self, off, size):
        if off == 0x24:                        # CNT
            return int(self._cnt) & 0xFFFF
        return super().read(off, size)

    def write(self, off, size, value):
        if off == 0x24:                        # CNT
            self._cnt = float(value & 0xFFFF)
            return
        if off == 0x10:                        # SR 写 0 清（w0c）
            self.regs[0x10] &= value & 0xFFFF if size == 2 else value
            return
        if off == 0x14:                        # EGR: UG 产生更新事件
            if value & 1:
                self._cnt = 0.0
                self._last_ns = self.now_ns
                self.regs[0x10] = self.regs.get(0x10, 0) | 1   # UIF
                self._apply_outputs()
            return
        super().write(off, size, value)
        if off in (0x00, 0x28, 0x2C, 0x18, 0x1C, 0x20, 0x44):
            # CR1/PSC/ARR/CCMR/CCER/BDTR 变化：重算输出
            self._apply_outputs()

    # ---------- 配置解析 ----------
    def _cr1(self): return self.regs.get(0x00, 0)
    def _psc(self): return self.regs.get(0x28, 0)
    def _arr(self): return self.regs.get(0x2C, 0)
    def _dier(self): return self.regs.get(0x0C, 0)
    def _sr(self): return self.regs.get(0x10, 0)
    def _moe_ok(self): return (self.regs.get(0x44, 0) & (1 << 15)) if self.advanced else 1

    def timclk_hz(self) -> float:
        return float(self.clock.apb_timer_clk(self.apb2))

    def _enabled(self):
        return (self._cr1() & 1) and self._arr() != 0 and self._clock_enabled

    def _ch_cfg(self, ch: int):
        """返回 (enable, polarity, mode)。mode: 6=PWM1 7=PWM2 3=toggle 0=off"""
        ccmr = self.regs.get(0x18 if ch <= 2 else 0x1C, 0)
        shift = (8 if ch in (2, 4) else 0)
        mode = (ccmr >> (shift + 4)) & 7
        ccer = self.regs.get(0x20, 0)
        en = (ccer >> (4 * (ch - 1))) & 1
        pol = (ccer >> (4 * (ch - 1) + 1)) & 1   # 1=反相
        return en, pol, mode

    def _ccr(self, ch: int):
        return self.regs.get(0x34 + 4 * (ch - 1), 0)

    # ---------- 时间推进（解析法展开边沿） ----------
    def step_to(self, now_ns):
        self.now_ns = now_ns
        if not self._enabled():
            self._cnt = int(self._cnt)
            self._last_ns = now_ns
            return
        psc, arr = self._psc(), self._arr()
        period = arr + 1
        tick_ns = (psc + 1) / self.timclk_hz() * 1e9
        dt = now_ns - self._last_ns
        if dt <= 0:
            return
        new = self._cnt + dt / tick_ns
        # 更新事件（溢出）
        if new >= period:
            k = int(new // period)
            if k > 0:
                self.regs[0x10] = self._sr() | 1               # UIF
                if self._dier() & 1:
                    self.irq(IRQ[self.up_irq])
                # OPM 单脉冲：停止
                if self._cr1() & (1 << 3):
                    self.regs[0x00] = self._cr1() & ~1
                    self._cnt = 0.0
                    self._last_ns = now_ns
                    self._apply_outputs()
                    return
        self._cnt = new % period
        self._last_ns = now_ns
        self._apply_outputs()

    def _apply_outputs(self):
        """按当前相位刷新所有通道输出电平（边沿经 net watcher 记时间戳）。"""
        if self.basic:
            return
        cnt = self._cnt
        arr = self._arr()
        moe = self._moe_ok()
        for ch in (1, 2, 3, 4):
            en, pol, mode = self._ch_cfg(ch)
            pin = _AF_PINS.get((self.index, ch))
            if not en or pin is None:
                continue
            ccr = self._ccr(ch)
            if not moe and self.advanced:
                lvl = 0
            elif mode == 6:                    # PWM1: CNT<CCR 高
                lvl = 1 if cnt < ccr else 0
                if ccr == 0:
                    lvl = 0
                elif ccr > arr:
                    lvl = 1
            elif mode == 7:                    # PWM2 反相
                lvl = 0 if cnt < ccr else 1
                if ccr == 0:
                    lvl = 1
                elif ccr > arr:
                    lvl = 0
            else:
                continue                        # 其他模式暂不驱动
            if pol:
                lvl ^= 1
            if self._out[ch - 1] != lvl:
                self._out[ch - 1] = lvl
                self.board.set_af_output(pin[0], pin[1], lvl)

    def next_event_ns(self):
        if not self._enabled():
            return None
        psc, arr = self._psc(), self._arr()
        period = arr + 1
        tick_ns = (psc + 1) / self.timclk_hz() * 1e9
        dt_to_overflow = (period - self._cnt) * tick_ns
        best = self.now_ns + dt_to_overflow
        if not self.basic:
            for ch in (1, 2, 3, 4):
                en, pol, mode = self._ch_cfg(ch)
                if en and mode in (6, 7):
                    ccr = self._ccr(ch)
                    if self._cnt < ccr <= arr:
                        t = self.now_ns + (ccr - self._cnt) * tick_ns
                        best = min(best, t)
        return best
