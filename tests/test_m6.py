"""M6: RTOS 期末考 — PendSV 上下文切换 + SVC 系统调用 + 双任务并发。

FreeRTOS ARM_CM3 端口的核心机制：
- SysTick 1ms -> ICSR.PENDSVSET -> PendSV(最低优先级) 在线程态完成切换
- PendSV: mrs psp / stmdb {r4-r11} 保存 / ldmia {r4-r11} / msr psp 恢复
- EXC_RETURN 0xFFFFFFFD 返回线程 PSP
- 首次启动路径（不保存，直接恢复任务0）
- SVC 从任务(PSP栈)发起，异常返回后任务无缝继续
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from zetsim.asm import Asm, Firmware
from zetsim.board import Board
from zetsim.engine import Simulation
from zetsim.devices import Led
from test_m1_m2 import crlh

TASK1_STACK = 0x20000800
TASK2_STACK = 0x20000C00
CUR_TASK = 0x20000000          # 当前任务号
FIRST_RUN = 0x20000004         # 首次运行标志
TASK_SP = 0x20000008           # uint32 任务栈指针[2]
SVC_COUNT = 0x20000010         # SVC 调用计数


def fw_rtos() -> Firmware:
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # --- 主线程初始化 ---
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, 4); a.orr(1, 2); a.str(1, 0, 0)     # GPIOA 时钟
    a.mov32(0, 0x40010800)
    a.mov32(1, crlh({4: 0x2, 5: 0x2})); a.str(1, 0, 0)            # PA4/PA5 输出
    # 首次标志=1
    a.mov32(0, FIRST_RUN); a.movs(1, 1); a.str(1, 0, 0)
    a.movs(1, 0); a.str(1, 0, 4)                                   # cur=0
    # 任务初始栈: [假r4-r11(8字)] + [异常帧(8字)]，sp 指向帧基址 = top-64+32
    a.mov32(0, TASK_SP)
    a.mov32(1, TASK1_STACK - 64); a.str(1, 0, 0)   # sp 指向假 r4-r11
    a.mov32(1, TASK2_STACK - 64); a.str(1, 0, 4)
    # 写初始帧（r2=帧地址, r3=任务入口）
    a.mov32(2, TASK1_STACK - 32)
    a.mov32(3, 0x08000400)                 # task1 入口
    a.bl("make_frame")
    a.mov32(2, TASK2_STACK - 32)
    a.mov32(3, 0x08000500)                 # task2 入口
    a.bl("make_frame")
    # PendSV 优先级最低 (SHPR3 byte3 = 0xFF)
    a.mov32(0, 0xE000ED20)
    a.movs(1, 0xFF); a.strb(1, 0, 3)
    # 切到 PSP（CONTROL.SPSEL=1），触发 PendSV
    a.mov32(0, 0x20004000)                # psp = 独立 scratch 栈（避免主线程压栈砸掉任务0初始帧）
    a.msr("PSP", 0)
    a.movs(0, 2); a.msr("CONTROL", 0)
    a.mov32(0, 0xE000ED04)
    a.mov32(1, 1 << 28); a.str(1, 0, 0)    # ICSR PENDSVSET
    # SysTick 1ms（PendSV 最低优先级，SysTick 默认 0 可抢占）
    a.mov32(0, 0xE000E010)
    a.movw(1, 7999); a.str(1, 0, 4)
    a.movs(1, 0); a.str(1, 0, 8)
    a.movs(1, 7); a.str(1, 0, 0)
    a.label("park")
    a.wfi(); a.bw("park")

    # --- 子程序：构造初始栈帧（r2=帧基址, r3=入口）---
    # 布局：[.. 假r4-r11(8字,清零) ..][帧 r0-r3,r12,lr,pc,xpsr]，r2 传入帧基址
    a.label("make_frame")
    a.subs(2, 32)                          # 下移到假 r4-r11 区
    a.movs(1, 0)
    a.str(1, 2, 0); a.str(1, 2, 4); a.str(1, 2, 8); a.str(1, 2, 12)
    a.str(1, 2, 16); a.str(1, 2, 20); a.str(1, 2, 24); a.str(1, 2, 28)
    a.adds(2, 32)                          # 回到帧基址
    a.str(1, 2, 0)                         # r0
    a.str(1, 2, 4); a.str(1, 2, 8)         # r1 r2
    a.str(1, 2, 12); a.str(1, 2, 16)       # r3 r12
    a.str(1, 2, 20)                        # lr
    a.str(3, 2, 24)                        # pc = 入口
    a.mov32(1, 0x01000000); a.str(1, 2, 28)  # xPSR: Thumb
    a.bx_lr()

    # --- SysTick handler @0x08000200: PENDSVSET ---
    st = Asm(0x08000200)
    st.mov32(0, 0xE000ED04)
    st.mov32(1, 1 << 28); st.str(1, 0, 0)
    st.bx_lr()

    # --- PendSV handler @0x08000240（r0 统一 = CUR_TASK=0x20000000 基址:
    #     [r0,#0]=cur, [r0,#4]=first_run, TASK_SP=0x20000008）---
    p = Asm(0x08000240)
    p.mov32(0, CUR_TASK)
    p.ldr(1, 0, 4)                         # first_run
    p.cmp(1, 0)
    p.beq("save_ctx")
    # 首次: first=0, 恢复任务0
    p.movs(1, 0); p.str(1, 0, 4)
    p.bw("restore")
    # --- 保存当前任务 ---
    p.label("save_ctx")
    p.mrs(2, "PSP")
    p.stmdb(2, [4, 5, 6, 7, 8, 9, 10, 11])
    p.ldr(1, 0, 0)                          # cur
    p.lsls(1, 1, 2)
    p.mov32(3, TASK_SP); p.adds_rr(3, 3, 1)
    p.str(2, 3, 0)                          # task_sp[cur] = psp
    # cur ^= 1
    p.ldr(1, 0, 0); p.movs(4, 1); p.eor(1, 4); p.str(1, 0, 0)
    # --- 恢复下一任务 ---
    p.label("restore")
    p.ldr(1, 0, 0)                          # cur
    p.lsls(1, 1, 2)
    p.mov32(3, TASK_SP); p.adds_rr(3, 3, 1)
    p.ldr(2, 3, 0)                          # next sp
    p.ldmia(2, [4, 5, 6, 7, 8, 9, 10, 11])
    p.msr("PSP", 2)
    p.bx_lr()

    # --- task1 @0x08000400: 每 ~5000 循环翻转 PA4 + SVC ---
    t1 = Asm(0x08000400)
    t1.mov32(0, 0x4001080C)
    t1.label("t1loop")
    t1.ldr(1, 0, 0); t1.movs(2, 0x10); t1.eor(1, 2); t1.str(1, 0, 0)
    t1.svc(0)                               # 每轮一次系统调用
    t1.mov32(3, 5000)
    t1.label("t1d")
    t1.subs(3, 1)
    t1.bne("t1d")
    t1.bw("t1loop")

    # --- task2 @0x08000500: 每 ~8000 循环翻转 PA5 ---
    t2 = Asm(0x08000500)
    t2.mov32(0, 0x4001080C)
    t2.label("t2loop")
    t2.ldr(1, 0, 0); t2.movs(2, 0x20); t2.eor(1, 2); t2.str(1, 0, 0)
    t2.mov32(3, 8000)
    t2.label("t2d")
    t2.subs(3, 1)
    t2.bne("t2d")
    t2.bw("t2loop")

    # --- SVC handler @0x08000580: SVC_COUNT++ ---
    sv = Asm(0x08000580)
    sv.mov32(0, SVC_COUNT)
    sv.ldr(1, 0, 0)
    sv.adds(1, 1)
    sv.str(1, 0, 0)
    sv.bx_lr()

    fw.add(0x08000100, a.assemble())
    fw.add(0x08000200, st.assemble())
    fw.add(0x08000240, p.assemble())
    fw.add(0x08000400, t1.assemble())
    fw.add(0x08000500, t2.assemble())
    fw.add(0x08000580, sv.assemble())
    # 主流程在 park 前需要使能 SysTick：插入到 make_frame 之后 —— 直接放进 a?
    fw.vector(15, 0x08000200)     # SysTick
    fw.vector(14, 0x08000240)     # PendSV
    fw.vector(11, 0x08000580)     # SVC
    return fw


def test_m6_context_switch():
    board = Board()
    board.reset()
    led4 = Led(board, "led4", "PA4")
    led5 = Led(board, "led5", "PA5")
    board.devices.update(led4=led4, led5=led5)
    fw = fw_rtos()
    board.core.load_segments(fw.build())
    sim = Simulation(board)
    rep = sim.run(until_ms=30, wall_timeout_s=60)

    pa4 = [e for e in board.events.query("gpio.PA4") if e.t_ns > 0]
    pa5 = [e for e in board.events.query("gpio.PA5") if e.t_ns > 0]
    svc_count = board.core.mem.read(SVC_COUNT, 4)
    assert len(pa4) >= 3, f"任务1 未运行或未翻转: {len(pa4)} 次"
    assert len(pa5) >= 1, f"任务2 未运行: {len(pa5)} 次"
    assert svc_count >= 3, f"SVC 系统调用未计数: {svc_count}"
    # 上下文真实交替：两个任务的翻转时间交错
    if len(pa4) >= 2 and len(pa5) >= 1:
        t4 = [e.t_ns for e in pa4]
        t5 = [e.t_ns for e in pa5]
        inter = any(t4[i] < t5[j] < t4[i + 1] for i in range(len(t4) - 1) for j in range(len(t5)))
        assert inter, "任务未交错运行（上下文切换可能失败）"


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
