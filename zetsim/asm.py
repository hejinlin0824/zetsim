"""zetsim.asm — 迷你 Thumb-2 汇编器（Cortex-M3 子集）.

为什么存在：目标机器上没有 arm 交叉编译器/Keil/keystone，
zetsim 需要一种完全自包含的方式生成测试固件。
所有编码按 ARMv7-M 手册实现，并用 unicorn 执行预言验证（见 tests/test_asm.py）。

用法:
    a = Asm(0x08000100)
    a.label("loop")
    a.movw(0, 0x1000); a.movt(0, 0x4001)   # r0 = 0x40011000
    a.ldr(1, 0, 8)                          # ldr r1,[r0,#8]
    a.b("loop")
    code = a.assemble()
"""
from __future__ import annotations

COND = {"eq": 0, "ne": 1, "cs": 2, "cc": 3, "mi": 4, "pl": 5, "vs": 6, "vc": 7,
        "hi": 8, "ls": 9, "ge": 10, "lt": 11, "gt": 12, "le": 13, "al": 14}

SYSM = {"APSR": 0, "IPSR": 5, "EPSR": 6, "IEPSR": 7, "MSP": 8, "PSP": 9,
        "PRIMASK": 16, "BASEPRI": 17, "FAULTMASK": 19, "CONTROL": 20}


class AsmError(Exception):
    pass


class Asm:
    """两遍式：emit 记录半字流 + 分支/字数据 fixup，assemble() 回填标签。"""

    def __init__(self, origin: int):
        self.origin = origin
        self.hw: list[int] = []            # 半字流（指令/数据混排）
        self.labels: dict[str, int] = {}   # name -> 半字索引
        self.fixups: list[tuple] = []      # (kind, hw_index, label, extra)

    # ---------- 基础 ----------
    @property
    def pc(self) -> int:  # 当前地址（半字对齐）
        return self.origin + 2 * len(self.hw)

    def label(self, name: str):
        if name in self.labels:
            raise AsmError(f"duplicate label {name}")
        self.labels[name] = len(self.hw)

    def _h(self, *halfwords: int):
        self.hw.extend(h & 0xFFFF for h in halfwords)

    def word(self, value: int):
        """嵌入一个 32 位数据字（非指令）。"""
        v = value & 0xFFFFFFFF
        self._h(v & 0xFFFF, v >> 16)

    def data(self, raw: bytes):
        """嵌入原始字节（自动半字对齐填充）。"""
        if len(self.hw) % 2 == 1:
            self._h(0)
        pad = len(raw) % 2
        out = bytearray(raw + (b"\x00" if pad else b""))
        for i in range(0, len(out), 2):
            self.hw.append(out[i] | (out[i + 1] << 8))

    def asciz(self, s: str):
        self.data(s.encode("ascii") + b"\x00")

    # ---------- 数据传送 ----------
    def movs(self, rd, imm):            self._h(0x2000 | (rd << 8) | (imm & 0xFF))
    def movs_reg(self, rd, rm):         self._h(0x0000 | (rm << 3) | rd)

    def _imm16_pair(self, op_f, rd, imm):
        imm &= 0xFFFF
        imm4, i, imm3, imm8 = imm >> 12, (imm >> 11) & 1, (imm >> 8) & 7, imm & 0xFF
        hw1 = op_f | (i << 10) | imm4
        hw2 = (imm3 << 12) | (rd << 8) | imm8
        self._h(hw1, hw2)

    def movw(self, rd, imm):            self._imm16_pair(0xF240, rd, imm)
    def movt(self, rd, imm):            self._imm16_pair(0xF2C0, rd, imm)
    def mov32(self, rd, value):
        """便捷：r = 32位立即数"""
        self.movw(rd, value & 0xFFFF)
        if (value >> 16) & 0xFFFF:
            self.movt(rd, value >> 16)

    def mov_hi(self, rd, rm):           self._h(0x4600 | (rm << 3) | rd)  # 限低寄存器

    def ldr(self, rt, rn, off=0):       self._h(0x6800 | ((off // 4 & 0x1F) << 6) | (rn << 3) | rt)
    def str(self, rt, rn, off=0):       self._h(0x6000 | ((off // 4 & 0x1F) << 6) | (rn << 3) | rt)
    def ldrb(self, rt, rn, off=0):      self._h(0x7800 | ((off & 0x1F) << 6) | (rn << 3) | rt)
    def strb(self, rt, rn, off=0):      self._h(0x7000 | ((off & 0x1F) << 6) | (rn << 3) | rt)
    def ldrh(self, rt, rn, off=0):      self._h(0x8800 | ((off // 2 & 0x1F) << 6) | (rn << 3) | rt)
    def strh(self, rt, rn, off=0):      self._h(0x8000 | ((off // 2 & 0x1F) << 6) | (rn << 3) | rt)
    def ldr_rr(self, rt, rn, rm):       self._h(0x5800 | (rm << 6) | (rn << 3) | rt)
    def str_rr(self, rt, rn, rm):       self._h(0x5000 | (rm << 6) | (rn << 3) | rt)

    def ldr_label(self, rt, label):
        """ldr rt, =label 地址（movw/movt 实现，无 literal pool）"""
        self.fixups.append(("imm32", len(self.hw), label, None))
        self._h(0, 0)

    # ---------- 算术 / 逻辑 ----------
    def adds(self, rd, imm):            self._h(0x3000 | (rd << 8) | (imm & 0xFF))
    def subs(self, rd, imm):            self._h(0x3800 | (rd << 8) | (imm & 0xFF))
    def adds3(self, rd, rn, imm3=0):    self._h(0x1C00 | ((imm3 & 7) << 6) | (rn << 3) | rd)
    def subs3(self, rd, rn, imm3=0):    self._h(0x1E00 | ((imm3 & 7) << 6) | (rn << 3) | rd)
    def adds_rr(self, rd, rn, rm):      self._h(0x1800 | (rm << 6) | (rn << 3) | rd)
    def subs_rr(self, rd, rn, rm):      self._h(0x1A00 | (rm << 6) | (rn << 3) | rd)
    def cmp(self, rn, imm):             self._h(0x2800 | (rn << 8) | (imm & 0xFF))
    def cmp_rr(self, rn, rm):           self._h(0x4280 | (rm << 3) | rn)
    def ands(self, rd, rm):             self._h(0x4000 | (rm << 3) | rd)
    def orr(self, rd, rm):              self._h(0x4300 | (rm << 3) | rd)
    def eor(self, rd, rm):              self._h(0x4040 | (rm << 3) | rd)
    def lsls(self, rd, rm, imm5):       self._h(0x0000 | ((imm5 & 0x1F) << 6) | (rm << 3) | rd)
    def lsrs(self, rd, rm, imm5):       self._h(0x0800 | ((imm5 & 0x1F) << 6) | (rm << 3) | rd)
    def muls(self, rd, rm):             self._h(0x4340 | (rm << 3) | rd)

    # ---- LDM/STM（32位，带写回）——FreeRTOS PendSV 上下文切换用 ----
    # 编码经暴力搜索+Unicorn 执行预言确认:
    #   STMDB rn!,{..}: hw1=0xE920|rn, hw2=纯寄存器掩码
    #   LDMIA rn!,{..}: hw1=0xE8B0|rn, hw2=纯寄存器掩码
    def _lm_mask(self, regs):
        m = 0
        for r in regs:
            m |= 1 << r
        return m

    def stmdb(self, rn, regs: list[int]):
        """stmdb rn!, {regs} —— 先减后存，写回"""
        self._h(0xE920 | rn, self._lm_mask(regs))

    def ldmia(self, rn, regs: list[int]):
        """ldmia rn!, {regs} —— 先读后增，写回"""
        self._h(0xE8B0 | rn, self._lm_mask(regs))

    # ---------- 分支 ----------
    def b(self, target, cond: str | None = None):
        idx = len(self.hw)
        if cond is None:
            self.fixups.append(("b11", idx, target, None))
            self._h(0xE000)
        else:
            self.fixups.append(("b8", idx, target, COND[cond]))
            self._h(0xD000)
        self.hw[idx] |= 0  # 占位

    def _bw_core(self, hw1, hw2base, target):
        # 计算 Thumb-2 分支立即数（B.W T4 / BL T1 共用编码布局）
        off = target - (self.origin + 2 * len(self.hw)) - 4
        if off & 1:
            raise AsmError("branch target not halfword aligned")
        imm25 = off >> 1                    # 范围 ±16MB
        s = (imm25 >> 24) & 1
        i1 = (imm25 >> 23) & 1
        i2 = (imm25 >> 22) & 1
        imm10 = (imm25 >> 12) & 0x3FF
        imm11 = imm25 & 0x7FF
        j1 = ((i1 ^ 1) ^ s) & 1
        j2 = ((i2 ^ 1) ^ s) & 1
        hw2 = hw2base | (j1 << 13) | (j2 << 11) | imm11
        self._h(hw1 | (s << 10) | imm10, hw2)

    def bw(self, target):
        if isinstance(target, str):
            self.fixups.append(("bw", len(self.hw), target, None))
            self._h(0xF000, 0x9000)
        else:
            self._bw_core(0xF000, 0x9000, target)

    def bl(self, target):
        if isinstance(target, str):
            self.fixups.append(("bl", len(self.hw), target, None))
            self._h(0xF000, 0xD000)
        else:
            self._bw_core(0xF000, 0xD000, target)

    def bx(self, rm):                     self._h(0x4700 | (rm << 3))
    def bx_lr(self):                      self._h(0x4770)

    # 常用条件分支便捷方法
    def beq(self, t): self.b(t, "eq")
    def bne(self, t): self.b(t, "ne")
    def bmi(self, t): self.b(t, "mi")
    def bpl(self, t): self.b(t, "pl")
    def bcs(self, t): self.b(t, "cs")
    def bcc(self, t): self.b(t, "cc")
    def bge(self, t): self.b(t, "ge")
    def blt(self, t): self.b(t, "lt")
    def bgt(self, t): self.b(t, "gt")
    def ble(self, t): self.b(t, "le")
    def bhi(self, t): self.b(t, "hi")

    # ---------- 栈 / 杂项 ----------
    def push(self, regs: list[int], lr=False):
        m = 0
        for r in regs:
            m |= 1 << r
        self._h(0xB400 | ((1 if lr else 0) << 8) | m)

    def pop(self, regs: list[int], pc=False):
        m = 0
        for r in regs:
            m |= 1 << r
        self._h(0xBC00 | ((1 if pc else 0) << 8) | m)

    def nop(self):                        self._h(0xBF00)
    def wfi(self):                        self._h(0xBF30)
    def svc(self, imm=0):                 self._h(0xDF00 | (imm & 0xFF))
    def bkpt(self, imm=0):                self._h(0xBE00 | (imm & 0xFF))
    def cpsid_i(self):                    self._h(0xB672)
    def cpsie_i(self):                    self._h(0xB662)
    def dmb(self):                        self._h(0xF3BF, 0x8F4F)
    def dsb(self):                        self._h(0xF3BF, 0x8F4E)
    def isb(self):                        self._h(0xF3BF, 0x8F53)

    def msr(self, sysm: str, rn: int):
        self._h(0xF380 | rn, 0x8000 | SYSM[sysm])

    def mrs(self, rd: int, sysm: str):
        self._h(0xF3EF, 0x8000 | (rd << 8) | SYSM[sysm])

    # ---------- 输出 ----------
    def assemble(self) -> bytes:
        for kind, idx, label, extra in self.fixups:
            if label not in self.labels:
                raise AsmError(f"undefined label {label}")
            target = self.origin + 2 * self.labels[label]
            here = self.origin + 2 * idx
            if kind == "b11":
                off = target - (here + 4)
                if not (-(2048) <= off <= 2046) or off & 1:
                    raise AsmError(f"b out of range ({off}) — use bw()")
                self.hw[idx] = 0xE000 | ((off >> 1) & 0x7FF)
            elif kind == "b8":
                off = target - (here + 4)
                if not (-256 <= off <= 254) or off & 1:
                    raise AsmError(f"b{extra} out of range ({off}) — use bw()")
                self.hw[idx] = 0xD000 | (extra << 8) | ((off >> 1) & 0xFF)
            elif kind in ("bw", "bl"):
                hw1, hw2base = self.hw[idx], (0x9000 if kind == "bw" else 0xD000)
                hw1 &= 0xFC00  # 去掉占位立即数位
                off = target - (here + 4)
                imm25 = off >> 1
                s = (imm25 >> 24) & 1
                i1, i2 = (imm25 >> 23) & 1, (imm25 >> 22) & 1
                imm10, imm11 = (imm25 >> 12) & 0x3FF, imm25 & 0x7FF
                j1 = ((i1 ^ 1) ^ s) & 1
                j2 = ((i2 ^ 1) ^ s) & 1
                self.hw[idx] = hw1 | (s << 10) | imm10
                self.hw[idx + 1] = hw2base | (j1 << 13) | (j2 << 11) | imm11
            elif kind == "imm32":
                self.movw  # noqa — fixup 在下方直接写
                imm = target & 0xFFFF
                imm4, i, imm3, imm8 = imm >> 12, (imm >> 11) & 1, (imm >> 8) & 7, imm & 0xFF
                self.hw[idx] = 0xF240 | (i << 10) | imm4
                self.hw[idx + 1] = (imm3 << 12) | (0 << 8) | imm8
                hi = target >> 16
                if hi:
                    h4, hi_, h3, h8 = hi >> 12, (hi >> 11) & 1, (hi >> 8) & 7, hi & 0xFF
                    # 原地补一条 movt：插入会破坏索引——imm32 fixup 只写 movw，
                    # 上层应使用 mov32；这里退化为只写低 16 位并断言
                    assert hi == 0 or True
                # 高 16 位：要求标签地址 < 0x10000 或上层用 mov32
                if target >> 16:
                    raise AsmError(f"ldr_label only supports <0x10000 (got {target:#x}); use mov32")
        out = bytearray()
        for h in self.hw:
            out += bytes([h & 0xFF, h >> 8])
        return bytes(out)


class Firmware:
    """构建最小 Cortex-M 固件镜像：向量表 + 代码段。

    vector[0]=SP, vector[1]=Reset(Thumb), 16+n = IRQ n, 15=SysTick。
    """

    def __init__(self, sp: int = 0x20005000, reset: int = 0x08000100, size: int = 0x10000):
        self.entries: list[int] = [0] * (size // 4)
        self.entries[0] = sp
        self.entries[1] = reset | 1
        self.segments: dict[int, bytes] = {}

    def vector(self, index: int, addr: int):
        self.entries[index] = addr | 1

    def add(self, addr: int, data: bytes):
        self.segments[addr] = data

    def build(self) -> dict[int, bytes]:
        used = 2
        for i, v in enumerate(self.entries):
            if v:
                used = max(used, i + 1)
        vt = b"".join(v.to_bytes(4, "little") for v in self.entries[:used])
        flash = bytearray(vt)
        for addr, data in self.segments.items():
            off = addr - 0x08000000
            if off < 0:
                raise AsmError(f"segment {addr:#x} outside flash")
            if off + len(data) > len(flash):
                flash.extend(b"\x00" * (off + len(data) - len(flash)))
            flash[off:off + len(data)] = data
        segs = {0x08000000: bytes(flash), 0x00000000: bytes(flash)}
        return segs

    def to_intel_hex(self) -> str:
        import io
        from intelhex import IntelHex
        ih = IntelHex()
        for base, data in self.build().items():
            ih.frombytes(data, offset=base)
        buf = io.StringIO()
        ih.tofile(buf, format="hex")
        return buf.getvalue()
