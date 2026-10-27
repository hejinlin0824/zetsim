"""CortexM3Core — Unicorn 封装 + NVIC 异常引擎（全项目最难也最核心的部分）。

机制（全部经微测试验证，见 tools/probe_unicorn.py）：
- MMIO：外设地址区映射为影子内存，UC_HOOK_MEM_READ 在取值前触发 ->
  钩子内把模型值写入影子内存，指令读到新鲜值（读副作用天然正确）。
- 异常入口：直接操纵 MSP/PSP/CONTROL/SP/LR/PC，按 ARMv7-M 手工压栈 8 字帧。
- 异常返回：BX LR / POP {pc} 到 EXC_RETURN 魔数 -> PC>=0xFFFFFFF0 + UcError，
  捕获后手工出栈。
- MSR/MRS/CPS 由 QEMU 原生执行（MSP/PSP/CONTROL/PRIMASK/BASEPRI 均可直接读写）。
- WFI(0xBF30)/SVC(0xDF00)/BKPT(0xBExx) 在代码钩子中拦截。
"""
from __future__ import annotations
import struct
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn import (UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                     UC_HOOK_MEM_INVALID, UC_HOOK_MEM_FETCH_UNMAPPED,
                     UC_MEM_FETCH_UNMAPPED)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                               UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                               UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
                               UC_ARM_REG_CPSR, UC_ARM_REG_MSP, UC_ARM_REG_PSP,
                               UC_ARM_REG_CONTROL, UC_ARM_REG_PRIMASK, UC_ARM_REG_BASEPRI)

EXC_NMI, EXC_HARDFAULT, EXC_SVCALL, EXC_PENDSV, EXC_SYSTICK = 2, 3, 11, 14, 15
IRQ_BASE = 16


class ActiveException:
    __slots__ = ("num", "prio")

    def __init__(self, num, prio):
        self.num, self.prio = num, prio


class MemoryBackend:
    def __init__(self, uc):
        self.uc = uc

    def read(self, addr, size):
        return int.from_bytes(self.uc.mem_read(addr, size), "little")

    def write(self, addr, size, value):
        self.uc.mem_write(addr, int(value).to_bytes(size, "little"))

    def read_bytes(self, addr, size):
        return bytes(self.uc.mem_read(addr, size))


class CortexM3Core:
    FLASH_BASE, FLASH_SIZE = 0x08000000, 0x80000      # 512KB
    SRAM_BASE, SRAM_SIZE = 0x20000000, 0x10000        # 64KB
    ALIAS_BASE, ALIAS_SIZE = 0x00000000, 0x10000
    PERIPH_BASE, PERIPH_SIZE = 0x40000000, 0x30000
    PPB_BASE, PPB_SIZE = 0xE000E000, 0x1000

    def __init__(self, bus, time_model):
        self.bus = bus
        self.time_model = time_model
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        self.mem = MemoryBackend(self.uc)
        bus.backend = self.mem
        self._map_memory()
        self._install_hooks()
        self.flash_bytes = bytearray(self.FLASH_SIZE)
        self.instr_count = 0
        self.now_ns = 0
        self.stop_reason: str | None = None
        self.last_error: UcError | None = None
        # 异常引擎状态
        self.active: list[ActiveException] = []
        self.nvic = None          # 注入 NVIC 模型
        self.vtor = 0
        self.fault_addr = None

    # ---------------- 内存与钩子 ----------------
    def _map_memory(self):
        uc = self.uc
        uc.mem_map(self.FLASH_BASE, self.FLASH_SIZE)
        uc.mem_map(self.SRAM_BASE, self.SRAM_SIZE)
        uc.mem_map(self.ALIAS_BASE, self.ALIAS_SIZE)
        uc.mem_map(self.PERIPH_BASE, self.PERIPH_SIZE)
        uc.mem_map(0x22000000, 0x2000000)    # SRAM bit-band
        uc.mem_map(0x42000000, 0x2000000)    # 外设 bit-band
        uc.mem_map(self.PPB_BASE, self.PPB_SIZE)

    def _install_hooks(self):
        uc = self.uc
        # 外设区 + bitband + PPB：读前注入 / 写转发
        for lo, hi in ((self.PERIPH_BASE, self.PERIPH_BASE + self.PERIPH_SIZE),
                       (0x42000000, 0x44000000),
                       (0x22000000, 0x24000000),
                       (self.PPB_BASE, self.PPB_BASE + self.PPB_SIZE)):
            uc.hook_add(UC_HOOK_MEM_READ, self._h_mmio_read, begin=lo, end=hi - 1)
            uc.hook_add(UC_HOOK_MEM_WRITE, self._h_mmio_write, begin=lo, end=hi - 1)
        uc.hook_add(UC_HOOK_MEM_INVALID, self._h_invalid)
        uc.hook_add(UC_HOOK_CODE, self._h_code)

    def _h_mmio_read(self, uc, access, addr, size, value, ud):
        try:
            v = self.bus.read(addr, size)
        except Exception as e:                                # 模型异常不能杀死仿真
            self.stop_reason = "model_error"
            self.last_error = e
            uc.emu_stop()
            v = 0
        uc.mem_write(addr, int(v).to_bytes(size, "little"))
        return True

    def _h_mmio_write(self, uc, access, addr, size, value, ud):
        try:
            self.bus.write(addr, size, value)
        except Exception as e:
            self.stop_reason = "model_error"
            self.last_error = e
            uc.emu_stop()
        return True

    def _h_invalid(self, uc, access, addr, size, value, ud):
        self.fault_addr = (access, addr, size)
        if access == UC_MEM_FETCH_UNMAPPED:
            self.stop_reason = "fetch_fault"
            uc.emu_stop()
            return False
        self.stop_reason = "data_fault"
        uc.emu_stop()
        return False

    def _h_code(self, uc, addr, size, ud):
        self.instr_count += 1
        fb = self.flash_bytes
        off = addr - self.FLASH_BASE
        if 0 <= off < len(fb) - 1:
            b0, b1 = fb[off], fb[off + 1]
        else:
            data = uc.mem_read(addr, 2)
            b0, b1 = data[0], data[1]
        if b1 == 0xBF:
            if b0 == 0x30:            # WFI
                self.stop_reason = "wfi"
                uc.emu_stop()
                return
        elif b1 == 0xDF and b0 == 0x00:   # SVC
            self.stop_reason = "svc"
            uc.emu_stop()
            return
        elif b1 == 0xBE:                   # BKPT
            self.stop_reason = "bkpt"
            uc.emu_stop()
            return

    # ---------------- 固件加载 ----------------
    def load_segments(self, segments: dict[int, bytes]):
        total = bytearray(self.FLASH_SIZE)
        for base, data in segments.items():
            if base == self.ALIAS_BASE:
                continue
            off = base - self.FLASH_BASE
            assert 0 <= off and off + len(data) <= len(total), f"segment {base:#x} 超出 Flash"
            total[off:off + len(data)] = data
        self.flash_bytes = total
        self.uc.mem_write(self.FLASH_BASE, bytes(total))
        self.uc.mem_write(self.ALIAS_BASE, bytes(total[: self.ALIAS_SIZE]))
        self.reset_cpu()

    def load_file(self, path: str):
        if path.lower().endswith(".hex"):
            from intelhex import IntelHex
            ih = IntelHex(path)
            segs = {}
            for start, end in ih.segments():
                segs[start] = bytes(ih.tobinarray(start=start, size=end - start))
            self.load_segments(segs)
        elif path.lower().endswith(".elf"):
            from elftools.elf.elffile import ELFFile
            segs = {}
            with open(path, "rb") as f:
                elf = ELFFile(f)
                for seg in elf.iter_segments():
                    if seg["p_type"] == "PT_LOAD":
                        segs[seg["p_paddr"] or seg["p_vaddr"]] = seg.data()
            self.load_segments(segs)
        else:
            raise ValueError(f"不支持的固件格式: {path}")

    def reset_cpu(self):
        uc = self.uc
        sp, reset = self.read_vector(0), self.read_vector(1)
        uc.reg_write(UC_ARM_REG_SP, sp)
        uc.reg_write(UC_ARM_REG_MSP, sp)
        uc.reg_write(UC_ARM_REG_PSP, 0)
        uc.reg_write(UC_ARM_REG_CONTROL, 0)
        uc.reg_write(UC_ARM_REG_PRIMASK, 0)
        uc.reg_write(UC_ARM_REG_BASEPRI, 0)
        uc.reg_write(UC_ARM_REG_PC, reset & ~1)
        self.pc_cur = reset & ~1
        self.active.clear()
        self.vtor = 0

    def read_vector(self, n) -> int:
        return int.from_bytes(self.uc.mem_read(self.vtor + 4 * n, 4), "little")

    # ---------------- 执行 ----------------
    REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
            UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
            UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
            UC_ARM_REG_R12]

    def run_slice(self, budget_instr: int):
        """执行至多 budget_instr 条指令。返回 (executed, stop_reason)。"""
        self.instr_count = 0
        self.stop_reason = None
        uc = self.uc
        try:
            uc.emu_start(self.pc_cur | 1, 0, 0, budget_instr)
            reason = self.stop_reason
        except UcError as e:
            self.last_error = e
            pc = uc.reg_read(UC_ARM_REG_PC)
            if pc >= 0xFFFFFFF0:
                reason = "exc_return"
            elif self.stop_reason in ("model_error",):
                reason = self.stop_reason
            elif pc == 0 and self.stop_reason == "data_fault":
                reason = "data_fault"
            else:
                reason = "error"
        else:
            if reason is None:
                reason = "budget"
        self.pc_cur = uc.reg_read(UC_ARM_REG_PC) & ~1
        return self.instr_count, reason

    # ---------------- 异常引擎（ARMv7-M） ----------------
    def execution_priority(self) -> int:
        """数值越小优先级越高；线程无激活异常时为 256。"""
        uc = self.uc
        if uc.reg_read(UC_ARM_REG_PRIMASK):
            return -1
        p = min((a.prio for a in self.active), default=256)
        bp = uc.reg_read(UC_ARM_REG_BASEPRI)
        if bp:
            p = min(p, bp)
        return p

    def exception_priority(self, num: int) -> int:
        return self.nvic.exception_priority(num)

    def dispatch_pending(self) -> int:
        """取出所有可执行的最高优先级 pending 异常（含抢占/尾链）。返回进入数量。"""
        n = 0
        while True:
            exc = self.nvic.highest_pending_enabled()
            if exc is None:
                break
            prio = self.exception_priority(exc)
            if prio >= self.execution_priority() and self.active:
                break
            if prio >= self.execution_priority() and not self.active and prio >= 256:
                break
            self.enter_exception(exc)
            n += 1
        return n

    def enter_exception(self, num: int, ret_pc: int | None = None):
        uc = self.uc
        # --- 选择线程当前栈 ---
        spsel = uc.reg_read(UC_ARM_REG_CONTROL) & 2
        sp = uc.reg_read(UC_ARM_REG_SP)
        was_psp = bool(spsel)
        # --- 压栈 {R0-R3,R12,LR,PC,xPSR} ---
        ret_pc = self.pc_cur if ret_pc is None else ret_pc
        xpsr = 0x01000000 | (uc.reg_read(UC_ARM_REG_CPSR) & 0xF8000000)
        frame = [uc.reg_read(r) for r in self.REGS[:4]]
        frame.append(uc.reg_read(UC_ARM_REG_R12))
        frame.append(uc.reg_read(UC_ARM_REG_LR))
        frame.append(ret_pc & ~1)
        frame.append(xpsr)
        pad = 1 if (sp & 4) else 0
        sp -= 32 + 4 * pad
        if pad:
            frame[7] |= 0x200                       # xPSR.bit9 STKALIGN
        uc.mem_write(sp, b"".join(struct.pack("<I", w) for w in frame))
        # --- 切换到 handler 栈（MSP） ---
        if was_psp:
            uc.reg_write(UC_ARM_REG_PSP, sp)
            uc.reg_write(UC_ARM_REG_CONTROL, uc.reg_read(UC_ARM_REG_CONTROL) & ~2)
        else:
            uc.reg_write(UC_ARM_REG_MSP, sp)
        uc.reg_write(UC_ARM_REG_SP, sp)
        # --- EXC_RETURN 与向量 ---
        uc.reg_write(UC_ARM_REG_LR, 0xFFFFFFFD if was_psp else 0xFFFFFFF9)
        vector = self.read_vector(num)
        uc.reg_write(UC_ARM_REG_PC, vector & ~1)
        self.pc_cur = vector & ~1
        prio = self.exception_priority(num)
        self.active.append(ActiveException(num, prio))
        self.nvic.on_entered(num)
        return num

    def exception_return(self) -> bool:
        """PC 停在 EXC_RETURN 魔数时出栈。成功返回 True。"""
        uc = self.uc
        magic = uc.reg_read(UC_ARM_REG_PC) | 1
        if magic not in (0xFFFFFFF1, 0xFFFFFFF9, 0xFFFFFFFD):
            return False
        use_psp = bool((magic >> 2) & 1)
        sp = uc.reg_read(UC_ARM_REG_PSP if use_psp else UC_ARM_REG_MSP)
        raw = uc.mem_read(sp, 32)
        r0, r1, r2, r3, r12, lr, pc, xpsr = struct.unpack("<8I", raw)
        new_sp = sp + 32 + (4 if (xpsr & 0x200) else 0)
        for reg, v in zip(self.REGS[:4], (r0, r1, r2, r3)):
            uc.reg_write(reg, v)
        uc.reg_write(UC_ARM_REG_R12, r12)
        uc.reg_write(UC_ARM_REG_LR, lr)
        # 恢复线程栈选择 + CPSR 标志位
        ctrl = uc.reg_read(UC_ARM_REG_CONTROL)
        ctrl = (ctrl | 2) if use_psp else (ctrl & ~2)
        uc.reg_write(UC_ARM_REG_CONTROL, ctrl)
        uc.reg_write(UC_ARM_REG_SP, new_sp)
        if use_psp:
            uc.reg_write(UC_ARM_REG_PSP, new_sp)
        else:
            uc.reg_write(UC_ARM_REG_MSP, new_sp)
        cpsr = uc.reg_read(UC_ARM_REG_CPSR)
        cpsr = (cpsr & ~0xF8000000) | (xpsr & 0xF8000000)
        uc.reg_write(UC_ARM_REG_CPSR, cpsr)
        uc.reg_write(UC_ARM_REG_PC, pc & ~1)
        self.pc_cur = pc & ~1
        if self.active:
            done = self.active.pop()
            self.nvic.on_exited(done.num)
        return True

    # ---------------- 诊断 ----------------
    def dump(self) -> dict:
        uc = self.uc
        regs = {f"r{i}": uc.reg_read(r) for i, r in enumerate(self.REGS)}
        regs.update({
            "sp": uc.reg_read(UC_ARM_REG_SP), "msp": uc.reg_read(UC_ARM_REG_MSP),
            "psp": uc.reg_read(UC_ARM_REG_PSP), "lr": uc.reg_read(UC_ARM_REG_LR),
            "pc": uc.reg_read(UC_ARM_REG_PC), "cpsr": uc.reg_read(UC_ARM_REG_CPSR),
            "control": uc.reg_read(UC_ARM_REG_CONTROL),
            "primask": uc.reg_read(UC_ARM_REG_PRIMASK),
            "basepri": uc.reg_read(UC_ARM_REG_BASEPRI),
        })
        return {"regs": regs, "active": [a.num for a in self.active],
                "stop_reason": self.stop_reason, "error": str(self.last_error) if self.last_error else None}
