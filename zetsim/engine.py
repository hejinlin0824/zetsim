"""Simulation — 仿真循环（时间片锁步 + 下一事件自适应 + WFI 快进 + 外部事件注入）。"""
from __future__ import annotations
import heapq
import time
from .core import EXC_HARDFAULT, EXC_SVCALL
from .periph.sysctrl import SysCtrl


class RunReport:
    def __init__(self):
        self.halt_reason: str = "timeout"
        self.time_ns: int = 0
        self.instructions: int = 0
        self.exceptions: int = 0
        self.error: str | None = None
        self.dump: dict | None = None

    def __repr__(self):
        return (f"<RunReport halt={self.halt_reason} t={self.time_ns/1e6:.3f}ms "
                f"instr={self.instructions:,} exceptions={self.exceptions} err={self.error}>")


class Simulation:
    def __init__(self, board, max_slice_ns: int = 100_000, min_slice_instr: int = 32):
        self.board = board
        self.core = board.core
        self.events = board.events
        self.max_slice_ns = max_slice_ns
        self.min_slice_instr = min_slice_instr
        self.sleeping = False
        self.halted = False
        self.halt_reason = None
        self.error = None
        self.on_slice = None                    # 前端回调（仪表盘/限速）
        self.report = RunReport()
        self._ext: list[tuple[int, int, object]] = []   # 外部注入事件堆
        self._ext_seq = 0

    # ---------- 外部事件 ----------
    def schedule(self, t_ns: int, fn):
        """在仿真时刻 t_ns 注入外部动作（按键、串口输入...）。"""
        self._ext_seq += 1
        heapq.heappush(self._ext, (int(t_ns), self._ext_seq, fn))

    def _next_ext_ns(self):
        return self._ext[0][0] if self._ext else None

    def _run_due_ext(self):
        while self._ext and self._ext[0][0] <= self.now:
            _, _, fn = heapq.heappop(self._ext)
            fn()

    # ---------- 主循环 ----------
    def run(self, until_ms: float | None = None, wall_timeout_s: float = 60.0,
            stop_on_bkpt: bool = True) -> RunReport:
        board, core = self.board, self.core
        t_start = time.time()
        # 每次调用都是新的一段仿真：清除上一次的停机状态（否则一次 halt 后永远跑不动）
        self.halted = False
        self.halt_reason = None
        self.report = RunReport()
        until_ns = self.now + until_ms * 1e6 if until_ms is not None else None
        instr_total = 0
        while not self.halted:
            if until_ns is not None and self.now >= until_ns:
                self.report.halt_reason = "timeout"
                break
            if time.time() - t_start > wall_timeout_s:
                self.report.halt_reason = "wall_timeout"
                break
            # --- 掉电：CPU 不执行，外设/器件时间照走（VDD/VSS 接回自动恢复） ---
            if not getattr(board, "mcu_power", True):
                self._set_time(self.now + self.max_slice_ns)
                for p_ in board.all_periphs():
                    p_.step_to(self.now)
                self._tick_devices()
                if self.on_slice:
                    self.on_slice(self.now)
                continue
            # --- 决定本片预算 ---
            nxt = None
            for p in board.all_periphs():
                e = p.next_event_ns()
                if e is not None and (nxt is None or e < nxt):
                    nxt = e
            ext = self._next_ext_ns()
            if ext is not None and (nxt is None or ext < nxt):
                nxt = ext
            target = self.now + self.max_slice_ns
            if nxt is not None and nxt > self.now:
                target = min(target, nxt + 1)
            budget = max(self.min_slice_instr,
                         int((target - self.now) * board.clock.sysclk_hz
                             / self.board.time_model.cpi / 1e9))
            # --- 执行 ---
            executed, reason = core.run_slice(budget)
            instr_total += executed
            self._advance_time(executed)
            for p in board.all_periphs():
                p.step_to(self.now)
            self._run_due_ext()
            self._tick_devices()
            if self.on_slice:
                self.on_slice(self.now)
            # --- 处理停因 ---
            if reason == "st_poll":
                # CPU 在原地轮询 SysTick COUNTFLAG：时间直接快进到
                # 定时到期或下一个事件（中断可打断），轮询零开销
                wake = None
                st = board.sysctrl.next_event_ns()
                if st is not None:
                    wake = st
                for p_ in board.all_periphs():
                    ev = p_.next_event_ns()
                    if ev is not None and (wake is None or ev < wake):
                        wake = ev
                ext = self._next_ext_ns()
                if ext is not None and (wake is None or ext < wake):
                    wake = ext
                if wake is None or wake <= self.now:
                    wake = self.now + 1_000
                self._set_time(wake)
                for p_ in board.all_periphs():
                    p_.step_to(self.now)
                self._run_due_ext()
                self._tick_devices()
            elif reason == "exc_return":
                if not core.exception_return():
                    self._halt("corrupt_exc_return", "EXC_RETURN 出栈失败")
                    break
                self.report.exceptions += 1
            elif reason == "svc":
                board.sysctrl.set_pending(EXC_SVCALL)
                core.pc_cur += 2                      # 返回地址 = SVC 之后
            elif reason == "wfi":
                self.sleeping = True
                if not self._sleep_until_event(until_ns, t_start, wall_timeout_s):
                    break
                self.sleeping = False
            elif reason == "bkpt":
                if stop_on_bkpt:
                    self._halt("bkpt", None)
                    break
                core.pc_cur += 2
            elif reason in ("fetch_fault", "data_fault", "error", "model_error"):
                if not self._try_hardfault(reason):
                    break
            # --- 派发中断 ---
            n = core.dispatch_pending()
            self.report.exceptions += n
        self.report.time_ns = self.now
        self.report.instructions = instr_total
        self.report.dump = core.dump()
        self.events.publish(self.now, "sim.halt", self.report.halt_reason)
        return self.report

    # ---------- WFI 快进 ----------
    def _sleep_until_event(self, until_ns, t_start, wall_timeout_s) -> bool:
        """睡眠线程直到有中断/外部注入。返回 False 表示仿真终止。"""
        board, core = self.board, self.core
        while True:
            # 先查 pending：按键等交互是外部线程直接改网络电平置起的，
            # 不经过事件堆——堆为空时也必须能被它唤醒
            exc = board.sysctrl.highest_pending_enabled()
            if exc is not None and self._can_preempt(exc):
                core.pc_cur += 2
                return True
            nxt = None
            for p in board.all_periphs():
                e = p.next_event_ns()
                if e is not None and (nxt is None or e < nxt):
                    nxt = e
            ext = self._next_ext_ns()
            if ext is not None and (nxt is None or ext < nxt):
                nxt = ext
            if nxt is None:
                if until_ns is not None:
                    self._set_time(max(self.now, until_ns))
                    for p in board.all_periphs():
                        p.step_to(self.now)
                    self._run_due_ext()
                    self._tick_devices()
                    self.report.halt_reason = "timeout"
                else:
                    self._halt("idle", "WFI 且无未来事件")
                return False
            if until_ns is not None and nxt > until_ns:
                self._set_time(until_ns)
                for p in board.all_periphs():
                    p.step_to(self.now)
                self.report.halt_reason = "timeout"
                return False
            self._set_time(nxt)
            for p in board.all_periphs():
                p.step_to(self.now)
            self._run_due_ext()
            self._tick_devices()
            if time.time() - t_start > wall_timeout_s:
                self.report.halt_reason = "wall_timeout"
                return False
            # 步进到事件点后可能新置起了 pending → 回到循环顶部统一判断

    def _can_preempt(self, exc) -> bool:
        prio = self.board.sysctrl.exception_priority(exc)
        return prio < self.core.execution_priority() or not self.core.active

    # ---------- HardFault ----------
    def _try_hardfault(self, reason: str) -> bool:
        core, board = self.core, self.board
        if EXC_HARDFAULT in [a.num for a in core.active]:
            self._halt("double_fault", f"{reason} @ {core.fault_addr}")
            return False
        vector = core.read_vector(EXC_HARDFAULT)
        if not vector:
            self._halt(reason, f"无 HardFault 处理程序，fault={core.fault_addr}, err={core.last_error}")
            return False
        board.sysctrl.set_pending(EXC_HARDFAULT)
        return True

    # ---------- 工具 ----------
    @property
    def now(self) -> int:
        return self.board.sysctrl.now_ns

    def _set_time(self, t_ns: int):
        self.board.sysctrl.now_ns = int(t_ns)
        self.core.now_ns = int(t_ns)

    def _advance_time(self, executed: int):
        cycles = executed * self.board.time_model.cpi
        ns = cycles / self.board.clock.sysclk_hz * 1e9
        # 覆盖 SysTick 的懒基准（由 step_to 统一处理）
        self._set_time(self.now + int(ns))
        self.core.now_ns = self.now

    def _tick_devices(self):
        for d in self.board.devices.values():
            tick = getattr(d, "sample", None) or getattr(d, "step", None)
            if tick:
                tick(self.now)

    def _halt(self, reason: str, error: str | None):
        self.halted = True
        self.halt_reason = reason
        self.report.halt_reason = reason
        self.report.error = error
