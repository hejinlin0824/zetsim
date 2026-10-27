"""ADC1/2/3 — 12 位逐次逼近（单次/连续/软件启动，EOC，IRQ，DMA 请求）。"""
from __future__ import annotations
from . import Peripheral
from .sysctrl import IRQ

_INST = {1: (0x40012400, 9, "ADC1_2"), 2: (0x40012800, 10, "ADC1_2"), 3: (0x40013C00, 15, "ADC3")}

# F1 通道 -> (端口, 引脚)：ch0-7=PA0-7, ch8-9=PB0-1, ch10-15=PC0-5
_CH_PINS = [(0, p) for p in range(8)] + [(1, 0), (1, 1)] + [(2, p) for p in range(6)]


class Adc(Peripheral):
    size = 0x50                # DR 在 0x4C，region 必须覆盖到 0x4F

    def __init__(self, index: int):
        super().__init__()
        base, en_bit, irq_name = _INST[index]
        self.base = base
        self.name = f"ADC{index}"
        self.irq_name = irq_name
        self.clock_gate = (0x18, en_bit)
        self.clock_gate_apb2 = True
        self._conv_done_ns = None
        self._dma = None
        self._started = False

    def reset(self):
        super().reset()
        self._conv_done_ns = None
        self._started = False

    # ---------- 配置 ----------
    def _cr2(self): return self.regs.get(0x08, 0)
    def _cr1(self): return self.regs.get(0x04, 0)

    def _first_channel(self) -> int:
        return self.regs.get(0x34, 0) & 0x1F          # SQR3 SQ1

    def _seq_len(self) -> int:
        return ((self.regs.get(0x2C, 0) >> 20) & 0xF) + 1   # SQR1 L

    def _channel_at(self, i: int) -> int:
        """规则序列第 i 个通道（i 从 0）。"""
        if i < 6:
            return (self.regs.get(0x34, 0) >> (i * 5)) & 0x1F
        if i < 12:
            return (self.regs.get(0x30, 0) >> ((i - 6) * 5)) & 0x1F
        return (self.regs.get(0x2C, 0) >> ((i - 12) * 5)) & 0x1F

    def _conv_ns(self, n_ch: int) -> float:
        clk = self.clock.adcclk_hz
        return 14.0 / clk * 1e9 * n_ch                 # 采样1.5+转换12.5 周期/通道

    def read(self, off, size):
        if off == 0x4C and self._started is False:
            pass
        return super().read(off, size)

    def write(self, off, size, value):
        super().write(off, size, value)
        if off == 0x08:                                # CR2
            cr2 = self._cr2()
            # ADON 0->1 启动（简化：第二次写 ADON 等同 SWSTART）
            if cr2 & (1 << 30):                        # SWSTART
                self._start()
                return
            if (cr2 & 1) and not self._started and not self._conv_done_ns:
                # ADON 置位：上电但不转换；SWSTART 或 EXTTRIG 才转
                pass

    # ---------- 转换流程 ----------
    def _start(self):
        if not self._cr2() & 1:                        # ADON 关
            return
        n = 1 if not (self._cr1() & (1 << 8)) else self._seq_len()   # SCAN
        self._conv_done_ns = self.now_ns + self._conv_ns(n)
        self.regs[0x00] = self.regs.get(0x00, 0) | (1 << 4)          # STRT

    def _complete(self):
        n = 1 if not (self._cr1() & (1 << 8)) else self._seq_len()
        # 规则序列只存最后值进 DR（F1 真实行为：非扫描存单通道）
        ch = self._channel_at(n - 1) if n > 1 else self._first_channel()
        self.regs[0x4C] = self._sample(ch) & 0xFFF
        self.regs[0x00] = self.regs.get(0x00, 0) | 2                # EOC
        self._conv_done_ns = None
        if self._cr1() & (1 << 5):                                  # EOCIE
            self.irq(IRQ[self.irq_name])
        if self._cr2() & (1 << 8) and self._dma:                    # DMA
            self._dma.request(self, self.dma_ch)
        if self._cr2() & 2:                                         # CONT
            self._start()

    dma_ch = 0        # ADC1 -> DMA1_CH1

    def _sample(self, ch: int) -> int:
        if ch < len(_CH_PINS):
            port, pin = _CH_PINS[ch]
            net = self.board.net(port, pin)
            v = net.voltage()
            if v is None:
                v = 3.3 if net.level == 1 else 0.0
            return int(round(v / 3.3 * 4095))
        return 0

    def step_to(self, now_ns):
        self.now_ns = now_ns
        if self._conv_done_ns is not None and now_ns >= self._conv_done_ns:
            self._complete()

    def next_event_ns(self):
        return self._conv_done_ns
