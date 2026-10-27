"""汇编器执行预言测试：每条编码在 unicorn 里真跑一遍验证。"""
import struct, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unicorn import *
from unicorn.arm_const import *
from zetsim.asm import Asm, Firmware

import pytest

def run(asm: Asm, *, regs=None, mem=None, count=200, expect_pc=None):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.mem_map(0x08000000, 0x20000)
    uc.mem_map(0x20000000, 0x10000)
    code = asm.assemble()
    uc.mem_write(asm.origin, code)
    halt = asm.origin + 0x800
    uc.mem_write(halt, bytes([0xFE, 0xE7]))          # b .
    regs = dict(regs or {})
    regs.setdefault("LR", halt | 1)   # Thumb 跳转目标 bit0 必须=1
    regs.setdefault("SP", 0x20008000)
    for r, v in (regs or {}).items():
        uc.reg_write(getattr(__import__("unicorn.arm_const", fromlist=["x"]), f"UC_ARM_REG_{r}"), v)
    for a, d in (mem or {}).items():
        uc.mem_write(a, d)
    uc.emu_start(asm.origin | 1, 0, 0, count)
    return uc

def reg(uc, r):
    return uc.reg_read(getattr(__import__("unicorn.arm_const", fromlist=["x"]), f"UC_ARM_REG_{r}"))

def test_movw_movt():
    a = Asm(0x08000100)
    a.mov32(0, 0x40011008); a.mov32(1, 0x12345678); a.bx_lr()
    uc = run(a)
    assert reg(uc, "R0") == 0x40011008
    assert reg(uc, "R1") == 0x12345678

def test_ldr_str_byte_half():
    a = Asm(0x08000100)
    a.mov32(2, 0x20000100)
    a.movs(0, 0xAB); a.strb(0, 2, 4)
    a.mov32(1, 0x1234); a.strh(1, 2, 8)
    a.mov32(3, 0xDEADBEEF); a.str(3, 2, 12)
    a.movs(0, 0); a.ldrb(0, 2, 4)
    a.movs(1, 0); a.ldrh(1, 2, 8)
    a.mov32(3, 0); a.ldr(3, 2, 12)
    a.bx_lr()
    uc = run(a)
    assert reg(uc, "R0") == 0xAB
    assert reg(uc, "R1") == 0x1234
    assert reg(uc, "R3") == 0xDEADBEEF

def test_ldr_rr():
    a = Asm(0x08000100)
    a.mov32(0, 0x20000100); a.movs(1, 4); a.ldr_rr(3, 0, 1); a.bx_lr()
    uc = run(a, mem={0x20000104: struct.pack("<I", 0x77)})
    assert reg(uc, "R3") == 0x77

def test_arith_cmp():
    a = Asm(0x08000100)
    a.movs(0, 10); a.adds(0, 5); a.subs(0, 3)      # 12
    a.movs(1, 3);  a.adds3(2, 1, 4)                # 7
    a.subs3(3, 2, 1)                                # 6
    a.adds_rr(4, 0, 2)                              # 19
    a.subs_rr(5, 4, 2)                              # 12
    a.ands(5, 1)                                    # 12&3=0
    a.orr(5, 1)                                     # 3
    a.eor(5, 1)                                     # 0
    a.muls(5, 2)                                    # 0*7=0
    a.cmp(0, 12)                                    # Z set
    a.bx_lr()
    uc = run(a)
    assert reg(uc, "R0") == 12 and reg(uc, "R2") == 7 and reg(uc, "R3") == 6
    assert reg(uc, "R4") == 19 and reg(uc, "R5") == 0
    assert reg(uc, "CPSR") & 0x40000000  # Z

def test_b_cond_and_far():
    a = Asm(0x08000100)
    a.movs(0, 0)
    a.label("loop")
    a.adds(0, 1)
    a.cmp(0, 5)
    a.b("loop", "ne")
    a.bw("done")
    a.movs(1, 0xFF)   # 不应执行
    a.nop()
    a.label("done")
    a.movs(2, 0x42)
    a.bx_lr()
    uc = run(a, count=100)
    assert reg(uc, "R0") == 5 and reg(uc, "R1") == 0 and reg(uc, "R2") == 0x42

def test_bl_push_pop():
    a = Asm(0x08000100)
    a.push([4, 5, 6, 7], lr=True)
    a.movs(4, 1)
    a.bl("sub1")
    a.pop([4, 5, 6, 7], pc=True)
    a.label("sub1")
    a.adds(4, 10)          # r4 = 11（被 push/pop 保护，最终恢复为 1）
    a.movs(0, 77)
    a.bx_lr()
    uc = run(a, regs={"R4": 0x11}, count=50)
    assert reg(uc, "R0") == 77
    assert reg(uc, "R4") == 0x11   # pop 恢复压栈时的旧值

def test_msr_mrs_psp():
    a = Asm(0x08000100)
    a.mov32(0, 0x20008000)
    a.msr("PSP", 0)
    a.mrs(1, "PSP")
    a.mov32(2, 0x20007700)
    a.msr("MSP", 2)
    a.mrs(3, "MSP")
    a.bx_lr()
    uc = run(a, regs={"SP": 0x20006000})
    assert reg(uc, "R1") == 0x20008000
    assert reg(uc, "R3") == 0x20007700
    assert reg(uc, "MSP") == 0x20007700 and reg(uc, "PSP") == 0x20008000

def test_lsls_lsrs():
    a = Asm(0x08000100)
    a.movs(0, 3); a.lsls(0, 0, 4)      # 48
    a.movs(1, 0xA0); a.lsrs(1, 1, 4)   # 10
    a.bx_lr()
    uc = run(a)
    assert reg(uc, "R0") == 48 and reg(uc, "R1") == 10

def test_firmware_hex_roundtrip(tmp_path):
    fw = Firmware(sp=0x20005000, reset=0x08000200)
    a = Asm(0x08000200)
    a.movs(0, 7); a.bx_lr()
    fw.add(0x08000200, a.assemble())
    hexstr = fw.to_intel_hex()
    p = tmp_path / "fw.hex"
    p.write_text(hexstr)
    from intelhex import IntelHex
    ih = IntelHex(str(p))
    assert ih[0x08000200] == 0x07 and ih[0x08000201] == 0x20
    assert ih[0x08000202] == 0x70 and ih[0x08000203] == 0x47
    # 向量表
    sp = int.from_bytes(bytes(ih[0x08000000 + i] for i in range(4)), "little")
    assert sp == 0x20005000
    rst = int.from_bytes(bytes(ih[0x08000004 + i] for i in range(4)), "little")
    assert rst == 0x08000201

if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
