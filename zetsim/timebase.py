"""时间模型与 F103 时钟树。

- TimeModel：指令 -> 周期（可替换：常量 CPI / 后期加权周期表）
- ClockTree：实时解析 RCC 寄存器，给出 SYSCLK/AHB/APB1/APB2/ADC 时钟。
  固件改 PLL/分频，外设频率即时真实变化 —— 功能级精度的关键。
"""
from __future__ import annotations


class ConstantTimeModel:
    """1 条指令 ≈ cpi 个周期（默认 2：Thumb-2 混合均值近似，含 Flash 等待态）。"""

    def __init__(self, cpi: float = 2.0):
        self.cpi = cpi

    def instruction_cost(self, addr: int, size: int) -> int:
        return self.cpi


class WeightedTimeModel:
    """按指令类别的加权周期表（M4 前后升级用，接口与常量模型一致）。"""

    def __init__(self):
        self.cpi = 1.5
        self.flash_wait = 2          # 72MHz 时 2 个等待周期

    def instruction_cost(self, addr: int, size: int) -> int:
        base = 2 if size == 2 else 4     # 粗分类：16 位 1~3 周期、32 位 2~5
        return base


class ClockTree:
    """依赖 RCC 外设的寄存器状态（避免循环依赖：构造后注入 rcc）。"""

    HSI_HZ = 8_000_000
    HSE_HZ = 8_000_000               # 假定 8MHz 晶振（常见 ZET6 板）

    def __init__(self):
        self.rcc = None              # 注入 RCC peripheral

    # --- 分频表（RM0008 表） ---
    @staticmethod
    def _hpresc(v: int) -> int:
        return [1, 2, 4, 8, 16, 64, 128, 256, 512][v]

    @staticmethod
    def _ppresc(v: int) -> int:
        return [1, 1, 2, 4, 8, 16][v] if v < 6 else 16

    @property
    def pllclk_hz(self) -> int:
        r = self.rcc
        cfgr = r.regs.get(0x04, 0)
        pllsrc = (cfgr >> 16) & 1
        pllmul = [(cfgr >> 18) & 0xF][0]
        mul = {0: 2, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9,
               8: 10, 9: 11, 10: 12, 11: 13, 12: 14, 13: 15, 14: 16}.get(pllmul, 16)
        if pllsrc == 0:
            return (self.HSI_HZ // 2) * mul
        xtpre = (cfgr >> 17) & 1
        hse = self.HSE_HZ // 2 if xtpre else self.HSE_HZ
        return hse * mul

    @property
    def sysclk_hz(self) -> int:
        r = self.rcc
        cr = r.regs.get(0x00, 0x83)          # 复位值 HSION
        cfgr = r.regs.get(0x04, 0)
        sw = cfgr & 3
        if sw == 0:
            return self.HSI_HZ
        if sw == 1:
            return self.HSE_HZ if (cr & (1 << 16) or True) else 0
        return self.pllclk_hz if (cr & (1 << 25)) else self.pllclk_hz

    @property
    def hclk_hz(self) -> int:
        cfgr = self.rcc.regs.get(0x04, 0)
        return self.sysclk_hz // self._hpresc((cfgr >> 4) & 0xF)

    @property
    def pclk1_hz(self) -> int:
        cfgr = self.rcc.regs.get(0x04, 0)
        return self.hclk_hz // self._ppresc((cfgr >> 8) & 7)

    @property
    def pclk2_hz(self) -> int:
        cfgr = self.rcc.regs.get(0x04, 0)
        return self.hclk_hz // self._ppresc((cfgr >> 11) & 7)

    @property
    def adcclk_hz(self) -> int:
        cfgr = self.rcc.regs.get(0x04, 0)
        div = [2, 4, 6, 8][(cfgr >> 14) & 3]
        return self.pclk2_hz // div

    def apb_timer_clk(self, apb2: bool) -> int:
        """定时器时钟：APB 分频为 1 时等于 PCLK，否则 x2（RM0008）。"""
        pclk = self.pclk2_hz if apb2 else self.pclk1_hz
        cfgr = self.rcc.regs.get(0x04, 0)
        presc = (cfgr >> 11) & 7 if apb2 else (cfgr >> 8) & 7
        return pclk * 2 if presc >= 4 else pclk
