"""SystemBus：地址解码 + bit-band 翻译 + MMIO 分发。"""
from __future__ import annotations


class Region:
    __slots__ = ("start", "size", "kind", "obj")

    def __init__(self, start, size, kind, obj=None):
        self.start, self.size, self.kind, self.obj = start, size, kind, obj

    @property
    def end(self):
        return self.start + self.size

    def __contains__(self, addr):
        return self.start <= addr < self.end


class StubRegion:
    """不支持的控制器（USB/CAN/SDIO/FSMC/RTC...）：读 0，写告警一次。"""
    def __init__(self, name):
        self.name = name
        self.warned = False

    def read(self, off, size):
        return 0

    def write(self, off, size, value):
        if not self.warned:
            self.warned = True


class SystemBus:
    def __init__(self):
        self.regions: list[Region] = []
        self.on_fault = None            # 引擎注入：非映射访问回调
        self.backend = None             # 注入 MemoryBackend（RAM/ROM 直通 unicorn 内存）

    def add(self, start, size, kind, obj=None):
        self.regions.append(Region(start, size, kind, obj))

    def find(self, addr) -> Region | None:
        for r in self.regions:
            if addr in r:
                return r
        return None

    # ---------- bit-band ----------
    SRAM_BB_BASE, SRAM_BB_END = 0x22000000, 0x24000000
    PERIPH_BB_BASE, PERIPH_BB_END = 0x42000000, 0x44000000

    def _bb_translate(self, addr):
        if self.SRAM_BB_BASE <= addr < self.SRAM_BB_END:
            ref, base = 0x20000000, self.SRAM_BB_BASE
        elif self.PERIPH_BB_BASE <= addr < self.PERIPH_BB_END:
            ref, base = 0x40000000, self.PERIPH_BB_BASE
        else:
            return None
        off = addr - base
        word = ref + (off >> 7)
        bit = (off >> 2) & 7
        return word, bit

    # ---------- 读写入口（CPU 钩子调用） ----------
    def read(self, addr, size) -> int:
        bb = self._bb_translate(addr)
        if bb:
            word, bit = bb
            return (self.read(word, 4) >> bit) & 1
        r = self.find(addr)
        if r is None:
            if self.on_fault:
                self.on_fault("read", addr, size)
            return 0
        if r.kind == "periph":
            return r.obj.read(addr - r.start, size)
        if r.kind == "stub":
            return r.obj.read(addr - r.start, size)
        if r.kind in ("ram", "rom"):
            return self.backend.read(addr, size)
        return 0

    def write(self, addr, size, value):
        bb = self._bb_translate(addr)
        if bb:
            word, bit = bb
            cur = self.read(word, 4)
            if value & 1:
                cur |= (1 << bit)
            else:
                cur &= ~(1 << bit)
            self.write(word, 4, cur)
            return
        r = self.find(addr)
        if r is None:
            if self.on_fault:
                self.on_fault("write", addr, size)
            return
        if r.kind == "periph":
            r.obj.write(addr - r.start, size, value)
            return
        if r.kind == "stub":
            r.obj.write(addr - r.start, size, value)
            return
        if r.kind == "ram":
            self.backend.write(addr, size, value)
