"""I2C1/2 — 主发送器状态机（RM0008 轮询流程，SSD1306 OLED 等）。

支持: PE/START/STOP, SB/ADDR/TXE/BTF 标志序列, SR2 BUSY/TRA。
主接收/10位地址未建模（见 docs/accuracy.md）。
"""
from __future__ import annotations
from . import Peripheral
from .sysctrl import IRQ

_INST = {1: (0x40005400, 21, "I2C1"), 2: (0x40005800, 22, "I2C2")}


class I2c(Peripheral):
    size = 0x24

    def __init__(self, index: int):
        super().__init__()
        base, en_bit, name = _INST[index]
        self.base = base
        self.name = name
        self.irq_name = name
        self.clock_gate = (0x1C, en_bit)
        self.clock_gate_apb2 = False
        self._state = "idle"                # idle/start/addr/data
        self._addr = 0
        self.devices: dict[int, object] = {}   # 7位地址 -> 器件
        self.bytes_tx = 0

    def reset(self):
        super().reset()
        self._state = "idle"
        self.bytes_tx = 0

    # ---------------- 状态机 ----------------
    def _dev(self):
        return self.devices.get(self._addr)

    def read(self, off, size):
        if off == 0x14:                     # SR1
            sr1 = self.regs.get(0x14, 0)
            if self._state == "start":
                sr1 |= 1                                    # SB
            elif self._state in ("addr", "data"):
                sr1 |= (1 << 7)                             # TXE
                if self._state == "addr":
                    sr1 |= 2                                # ADDR
                sr1 |= 4                                    # BTF（即时完成简化）
            return sr1
        if off == 0x18:                     # SR2：读它清 ADDR
            sr2 = 1                                         # MSL
            if self._state != "idle":
                sr2 |= (1 << 1)                             # BUSY
                sr2 |= (1 << 2)                             # TRA（发送）
            if self._state == "addr":
                self._state = "data"
                dev = self._dev()
                if dev:
                    dev.repeat_start() if hasattr(dev, "repeat_start") else None
            return sr2
        return super().read(off, size)

    def write(self, off, size, value):
        if off == 0x00:                     # CR1
            pe = value & 1
            # START(8)/STOP(9) 是触发位：动作后清零（真机自清），不留在读回值里
            if value & (1 << 8):
                self._state = "start"
                self._addr = 0
            if value & (1 << 9):
                dev = self._dev()
                if dev:
                    dev.stop()
                self._state = "idle"
            self.regs[0x00] = value & ~0x300 & 0xFFFF
            if not pe:
                self._state = "idle"
            return
        if off == 0x10:                     # DR
            if self._state == "start":
                self._addr = (value >> 1) & 0x7F
                dev = self._dev()
                ack = dev.start(self._addr, read=bool(value & 1)) if dev else False
                self._state = "addr" if (ack or value & 1 == 0) else "idle"
                if not ack:
                    self.regs[0x14] = self.regs.get(0x14, 0) | (1 << 10)   # AF
                else:
                    self.regs[0x14] = self.regs.get(0x14, 0) & ~(1 << 10)
            elif self._state == "data":
                dev = self._dev()
                if dev:
                    dev.write(value & 0xFF)
                self.bytes_tx += 1
            return
        super().write(off, size, value)
