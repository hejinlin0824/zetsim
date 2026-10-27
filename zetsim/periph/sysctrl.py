"""SysCtrl — SysTick + NVIC + SCB（0xE000E000-0xE000EFFF，PPB 区）。

与 core.CortexM3Core 的异常引擎配合：
- 外设 pend -> set_pending() -> 引擎 dispatch_pending() 决定是否/何时进入
- 优先级：F1 实现 4 位（IPR 高 nibble），AIRCR.PRIGROUP 分组，数值小者优先
"""
from __future__ import annotations
from . import Peripheral
from ..core import EXC_HARDFAULT, EXC_SVCALL, EXC_PENDSV, EXC_SYSTICK

N_EXT_IRQ = 60          # F103 高容量：60 个外部 IRQ

IRQ = {
    "WWDG": 0, "PVD": 1, "TAMPER": 2, "RTC": 3, "FLASH": 4, "RCC": 5,
    "EXTI0": 6, "EXTI1": 7, "EXTI2": 8, "EXTI3": 9, "EXTI4": 10,
    "DMA1_CH1": 11, "DMA1_CH2": 12, "DMA1_CH3": 13, "DMA1_CH4": 14, "DMA1_CH5": 15,
    "DMA1_CH6": 16, "DMA1_CH7": 17, "ADC1_2": 18,
    "USB_HP_CAN_TX": 19, "USB_LP_CAN_RX0": 20, "CAN_RX1": 21, "CAN_SCE": 22,
    "EXTI9_5": 23, "TIM1_BRK": 24, "TIM1_UP": 25, "TIM1_TRG_COM": 26, "TIM1_CC": 27,
    "TIM2": 28, "TIM3": 29, "TIM4": 30, "TIM5": 50,
    "SPI1": 35, "SPI2": 36, "SPI3": 51,
    "USART1": 37, "USART2": 38, "USART3": 39, "UART4": 52, "UART5": 53,
    "EXTI15_10": 40, "RTCAlarm": 41, "USBWakeUp": 42, "TIM8_BRK": 43, "TIM8_UP": 44,
    "TIM8_TRG_COM": 45, "TIM8_CC": 46, "ADC3": 47, "FSMC": 48, "SDIO": 49,
    "TIM6": 54, "TIM7": 55, "DMA2_CH1": 56, "DMA2_CH2": 57, "DMA2_CH3": 58,
    "DMA2_CH4": 59, "DMA2_CH5": 60,
}
IRQ_NAME = {v: k for k, v in IRQ.items()}


class SysCtrl(Peripheral):
    name = "SYSCtrl"
    base = 0xE000E000
    size = 0x1000

    def __init__(self):
        super().__init__()
        self.core = None
        self.sys_pend: set[int] = set()
        self.sys_active: set[int] = set()
        self._iser = [0, 0]
        self._ispr = [0, 0]
        self._st_val = 0.0            # SysTick 懒计数（浮点精确）
        self._st_base_ns = 0
        self._st_countflag = False

    def reset(self):
        super().reset()
        self.sys_pend.clear()
        self.sys_active.clear()
        self._iser = [0, 0]
        self._ispr = [0, 0]
        self._st_val = 0.0
        self._st_base_ns = 0
        self._st_countflag = False
        self.regs[0xD00] = 0x411FC231        # CPUID: Cortex-M3

    # ---------------- 总线读写 ----------------
    def read(self, off, size):
        if 0x100 <= off < 0x120:
            return self._iser[(off - 0x100) // 4]
        if 0x180 <= off < 0x1A0:
            return self._iser[(off - 0x180) // 4]
        if 0x200 <= off < 0x220:
            return self._ispr[(off - 0x200) // 4]
        if 0x280 <= off < 0x2A0:
            return self._ispr[(off - 0x280) // 4]
        if off == 0x10:                       # SysTick CTRL（COUNTFLAG=bit16 读清）
            cf = 1 if self._st_countflag else 0
            self._st_countflag = False
            return self.regs.get(0x10, 0) | (cf << 16)
        if off == 0x18:                       # SysTick VAL
            return int(self._st_val) & 0xFFFFFF
        if off == 0xD04:                      # ICSR 读
            act = self.core.active[-1].num if self.core.active else 0
            pend = self.highest_pending_enabled()
            v = act & 0x1FF
            if pend is not None:
                v |= (pend & 0x1FF) << 12
            if len(self.core.active) <= 1:
                v |= 1 << 11                  # RETTOBASE
            return v
        return super().read(off, size)

    def write(self, off, size, value):
        if off == 0xD04:                     # ICSR（SCB 区）
            if value & (1 << 28):
                self.sys_pend.add(EXC_PENDSV)
            if value & (1 << 27):
                self.sys_pend.discard(EXC_PENDSV)
            if value & (1 << 26):
                self.sys_pend.add(EXC_SYSTICK)
            if value & (1 << 25):
                self.sys_pend.discard(EXC_SYSTICK)
            return
        if off == 0xD08:                     # VTOR
            v = value & 0xFFFFE000
            self.regs[0xD08] = v
            self.core.vtor = v
            return
        if off == 0x10:                       # SysTick CTRL
            self._st_base_ns = self.now_ns
            self.regs[0x10] = value & 7
            return
        if off == 0x18:                       # VAL 写 0
            self._st_val = 0.0
            self._st_base_ns = self.now_ns
            return
        if off == 0x14:                       # LOAD
            self.regs[0x14] = value & 0xFFFFFF
            return
        if 0x100 <= off < 0x120:
            self._iser[(off - 0x100) // 4] |= value
            return
        if 0x180 <= off < 0x1A0:
            self._iser[(off - 0x180) // 4] &= ~value
            return
        if 0x200 <= off < 0x220:
            self._ispr[(off - 0x200) // 4] |= value
            return
        if 0x280 <= off < 0x2A0:
            self._ispr[(off - 0x280) // 4] &= ~value
            return
        super().write(off, size, value)

    # ---------------- SysTick ----------------
    def _st_freq(self):
        clk = self.clock.hclk_hz
        return clk if (self.regs.get(0x10, 0) & 4) else clk / 8

    def _st_tick_ns(self) -> float:
        return 1e9 / self._st_freq()

    def step_to(self, now_ns):
        ctrl = self.regs.get(0x10, 0)
        load = self.regs.get(0x14, 0)
        self.now_ns = now_ns
        if not (ctrl & 1) or load == 0:
            self._st_base_ns = now_ns
            return
        # VAL=0 时下一拍静默重载 LOAD（RM0008：写 VAL 清零后先重载再倒数）
        if self._st_val == 0:
            self._st_val = float(load + 1)
        tick = self._st_tick_ns()
        dt = now_ns - self._st_base_ns
        v = self._st_val - dt / tick
        wraps = 0
        if v <= 0:
            wraps = int(-v // (load + 1)) + 1
            v += wraps * (load + 1)
            if v > load + 1:
                v -= load + 1
                wraps -= 1
        if wraps > 0:
            self._st_countflag = True
            if ctrl & 2:
                self.sys_pend.add(EXC_SYSTICK)
        self._st_val = v
        self._st_base_ns = now_ns

    def next_event_ns(self):
        ctrl = self.regs.get(0x10, 0)
        load = self.regs.get(0x14, 0)
        if not (ctrl & 1) or load == 0:
            return None
        return self.now_ns + self._st_val * self._st_tick_ns()

    # ---------------- NVIC ----------------
    def set_pending(self, exception_num: int, on: bool = True):
        if exception_num >= 16:
            i = exception_num - 16
            if on:
                self._ispr[i // 32] |= 1 << (i % 32)
            else:
                self._ispr[i // 32] &= ~(1 << (i % 32))
        else:
            (self.sys_pend.add if on else self.sys_pend.discard)(exception_num)

    def is_pending(self, exception_num: int) -> bool:
        if exception_num >= 16:
            i = exception_num - 16
            return bool(self._ispr[i // 32] & (1 << (i % 32)))
        return exception_num in self.sys_pend

    def is_enabled(self, exception_num: int) -> bool:
        if exception_num >= 16:
            i = exception_num - 16
            return bool(self._iser[i // 32] & (1 << (i % 32)))
        return True            # 系统异常总是可进入

    def _enabled_pends(self):
        for i in range(N_EXT_IRQ):
            bit = 1 << (i % 32)
            if (self._ispr[i // 32] & bit) and (self._iser[i // 32] & bit):
                yield 16 + i
        yield from sorted(self.sys_pend)

    def highest_pending_enabled(self):
        best, best_key = None, None
        for n in self._enabled_pends():
            key = (self.exception_priority(n), n)
            if best_key is None or key < best_key:
                best, best_key = n, key
        return best

    def exception_priority(self, num: int) -> int:
        if num >= 16:
            b = self._ipr_get(num - 16)
        elif num == EXC_SYSTICK:
            b = (self.regs.get(0xD20, 0) >> 24) & 0xFF
        elif num == EXC_PENDSV:
            b = (self.regs.get(0xD20, 0) >> 16) & 0xFF
        elif num == EXC_SVCALL:
            b = (self.regs.get(0xD1C, 0) >> 24) & 0xFF
        elif num == EXC_HARDFAULT:
            b = 0
        else:
            b = 0xFF
        group = min((self.regs.get(0xD0C, 0) >> 8) & 7, 4)
        pre = (b >> 4) >> group
        sub = ((b >> 4) & ((1 << group) - 1)) if group else 0
        return (pre << 4) | sub

    def _ipr_get(self, irq: int) -> int:
        w = self.regs.get(0x400 + (irq // 4) * 4, 0)
        return (w >> ((irq % 4) * 8)) & 0xFF

    def on_entered(self, num: int):
        self.set_pending(num, False)
        if num < 16:
            self.sys_active.add(num)

    def on_exited(self, num: int):
        self.sys_active.discard(num)
