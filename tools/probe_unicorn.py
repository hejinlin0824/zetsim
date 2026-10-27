"""Unicorn capability probes — these decide zetsim's core mechanisms."""
import struct
from unicorn import *
from unicorn.arm_const import *

def hw(*vals):  # halfwords -> little-endian bytes
    return b"".join(struct.pack("<H", v) for v in vals)

def mkuc():
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.mem_map(0x08000000, 0x20000)   # flash
    uc.mem_map(0x20000000, 0x10000)   # sram
    return uc

print("=== A: unmapped MMIO read injection (map+write+True in MEM_INVALID) ===")
uc = mkuc()
prog = hw(0xF241, 0x0100, 0xF2C4, 0x0101, 0x6848, 0xE7FE)  # movw r1,#0x1000; movt r1,#0x4001; ldr r0,[r1,#8]; bkpt
uc.mem_write(0x08000000, prog)
seen = {}
def on_invalid(uc, access, address, size, value, ud):
    seen['a'] = (access, address, size)
    if access == UC_MEM_READ_UNMAPPED:
        uc.mem_map(address & ~0xFFF, 0x1000)
        uc.mem_write(address, struct.pack("<I", 0xDEADBEEF))
        return True
    return False
uc.hook_add(UC_HOOK_MEM_INVALID, on_invalid)
uc.emu_start(0x08000000|1, 0, 0, 10)
print("  hook saw:", seen, "r0 =", hex(uc.reg_read(UC_ARM_REG_R0)))
print("  VERDICT:", "INJECTION WORKS" if uc.reg_read(UC_ARM_REG_R0) == 0xDEADBEEF else "FAILED")

print("=== B: WFI behavior ===")
uc2 = mkuc()
uc2.mem_write(0x08000000, hw(0xBF30, 0xE7FE))  # wfi; bkpt
try:
    uc2.emu_start(0x08000000|1, 0, 0, 100)
    print("  emu_start returned, PC =", hex(uc2.reg_read(UC_ARM_REG_PC)))
except UcError as e:
    print("  UcError:", e, "PC =", hex(uc2.reg_read(UC_ARM_REG_PC)))

print("=== C: CPSR layout in Thumb ===")
uc3 = mkuc()
uc3.mem_write(0x08000000, hw(0xBF00, 0xE7FE))
uc3.emu_start(0x08000000|1, 0, 0, 10)
print("  CPSR =", hex(uc3.reg_read(UC_ARM_REG_CPSR)), "(T bit at bit24 =", bool(uc3.reg_read(UC_ARM_REG_CPSR) & (1 << 24)), ")")

print("=== D: count semantics ===")
uc4 = mkuc()
uc4.mem_write(0x08000000, hw(0xBF00, 0xBF00, 0xBF00, 0xE7FE))
uc4.emu_start(0x08000000|1, 0, 0, 2)
print("  after count=2, PC =", hex(uc4.reg_read(UC_ARM_REG_PC)), "(start+4 =", hex(0x08000004), ")")

print("=== E: exception return magic -> fetch fault at 0xFFFFFFFC ===")
uc5 = mkuc()
uc5.mem_map(0x0, 0x10000)                      # boot alias / vector area
uc5.mem_write(0x0, hw(0xE7FE))                 # vector slot 0 (unused here)
HANDLER = 0x08000100
uc5.mem_write(HANDLER, hw(0x4770))             # bx lr
uc5.mem_write(0x08000000, hw(0xE7FE))
uc5.reg_write(UC_ARM_REG_SP, 0x20001000)
uc5.reg_write(UC_ARM_REG_LR, 0xFFFFFFFD)       # EXC_RETURN: return to thread/PSP
uc5.reg_write(UC_ARM_REG_PC, HANDLER)
got = {}
def on_fetch_inv(uc, access, address, size, value, ud):
    got['a'] = (access, address)
    uc.emu_stop()
    return False
uc5.hook_add(UC_HOOK_MEM_FETCH_UNMAPPED, on_fetch_inv)
try:
    uc5.emu_start(HANDLER|1, 0, 0, 10)
except UcError as e:
    print("  err:", e)
print("  fetch fault at:", hex(got.get('a', (0, 0))[1]), "PC =", hex(uc5.reg_read(UC_ARM_REG_PC)))

print("=== F: MSP/PSP/CONTROL read-write ===")
uc6 = mkuc()
uc6.reg_write(UC_ARM_REG_MSP, 0x20008000)
uc6.reg_write(UC_ARM_REG_PSP, 0x20004000)
print("  MSP =", hex(uc6.reg_read(UC_ARM_REG_MSP)), " PSP =", hex(uc6.reg_read(UC_ARM_REG_PSP)),
      " CONTROL =", uc6.reg_read(UC_ARM_REG_CONTROL), " SP =", hex(uc6.reg_read(UC_ARM_REG_SP)))
uc6.reg_write(UC_ARM_REG_CONTROL, 2)  # SPSEL=1 -> use PSP
print("  after CONTROL=2: SP =", hex(uc6.reg_read(UC_ARM_REG_SP)), "(expect PSP 0x20004000)")

print("=== G: mapped-write hook fires? ===")
uc7 = mkuc()
uc7.mem_write(0x08000000, hw(0x2101, 0x6001, 0xE7FE))  # movs r1,#1; str r1,[r0,#0]; bkpt
uc7.reg_write(UC_ARM_REG_R0, 0x20000100)
w = []
uc7.hook_add(UC_HOOK_MEM_WRITE, lambda uc, a, addr, size, val, ud: w.append((addr, val)), begin=0x20000000, end=0x2000FFFF)
uc7.emu_start(0x08000000|1, 0, 0, 10)
print("  write hook:", [(hex(a), v) for a, v in w])

print("=== H: read hook on mapped mem (side-effect reads) ===")
uc8 = mkuc()
uc8.mem_write(0x08000000, hw(0x6800, 0xE7FE))  # ldr r0,[r0,#0]; bkpt
uc8.mem_write(0x20000100, struct.pack("<I", 0x55))
uc8.reg_write(UC_ARM_REG_R0, 0x20000100)
r = []
uc8.hook_add(UC_HOOK_MEM_READ, lambda uc, a, addr, size, val, ud: r.append((addr, val)), begin=0x20000000, end=0x2000FFFF)
uc8.emu_start(0x08000000|1, 0, 0, 10)
print("  read hook:", [(hex(a), hex(v)) for a, v in r], "r0 =", hex(uc8.reg_read(UC_ARM_REG_R0)))

print("=== I: speed: 2M nops with code hook ===")
import time
uc9 = mkuc()
uc9.mem_write(0x08000000, b"\x00\xbf" * 0x20000)  # nops
cnt = [0]
def tick(uc, a, s, ud): cnt[0] += 1
uc9.hook_add(UC_HOOK_CODE, tick)
t0 = time.time()
try:
    uc9.emu_start(0x08000000|1, 0, 2000, 2_000_000)
except UcError as e:
    print("  err:", e)
dt = time.time() - t0
print(f"  {cnt[0]:,} instrs in {dt:.2f}s = {cnt[0]/dt/1e6:.2f}M instr/s (with py code hook)")

print("=== J: MSR/MRS executed by QEMU natively? ===")
uc10 = mkuc()
# msr msp, r0 ; mrs r1, msp ; bkpt   -- encodings per ARMv7-M
# MSR: F380|Rn 8008  (SYSm=8 MSP)   MRS: F3EF 8008|Rd? -> test both common forms
uc10.mem_write(0x08000000, hw(0xF381, 0x8008, 0xF3EF, 0x8108, 0xE7FE))  # msr msp,r1 ; mrs r1?,msp
uc10.reg_write(UC_ARM_REG_R1, 0x2000ABCD)
try:
    uc10.emu_start(0x08000000|1, 0, 0, 10)
except UcError as e:
    print("  err:", e)
print("  MSP =", hex(uc10.reg_read(UC_ARM_REG_MSP)), "(expect 0x2000ABCD if msr worked; R1 =", hex(uc10.reg_read(UC_ARM_REG_R1)), ")")
