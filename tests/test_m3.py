"""M3: EXTI 按键中断 + NVIC 使能/优先级。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from zetsim.asm import Asm, Firmware
from zetsim.board import Board
from zetsim.engine import Simulation
from zetsim.devices import Led, Button
from test_m1_m2 import crlh


def fw_exti_button() -> Firmware:
    """PA0 按键输入，上升沿 EXTI0 中断翻转 PA5。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # RCC APB2ENR |= GPIOA(2) | AFIO(0)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0)
    a.movs(2, 5)                       # (1<<2)|(1<<0)
    a.orr(1, 2); a.str(1, 0, 0)
    # PA5 输出
    a.mov32(0, 0x40010800)
    a.mov32(1, crlh({5: 0x2})); a.str(1, 0, 0)
    # EXTI: IMR |= 1<<0, RTSR |= 1<<0 (PA0 上升沿)
    a.mov32(0, 0x40010400)
    a.movs(1, 1); a.str(1, 0, 0)       # IMR
    a.movs(1, 1); a.str(1, 0, 8)       # RTSR
    # AFIO EXTICR1 = 0 (EXTI0 -> PA)
    # NVIC ISER0 |= 1<<6 (EXTI0 = IRQ6)
    a.mov32(0, 0xE000E100)
    a.mov32(1, 1 << 6)
    a.str(1, 0, 0)
    # 空闲
    a.label("idle")
    a.wfi(); a.bw("idle")

    # --- EXTI0_Handler @ 0x08000180 ---
    h = Asm(0x08000180)
    h.mov32(0, 0x4001080C)             # GPIOA ODR
    h.ldr(1, 0, 0)
    h.movs(2, 0x20); h.eor(1, 2)
    h.str(1, 0, 0)
    # 清 pending: EXTI_PR w1c bit0
    h.mov32(0, 0x40010414)
    h.movs(1, 1); h.str(1, 0, 0)
    h.bx_lr()
    fw.add(0x08000100, a.assemble())
    fw.add(0x08000180, h.assemble())
    fw.vector(22, 0x08000180)          # EXTI0 = IRQ6 -> 异常 22
    return fw


def test_m3_button_exti_interrupt():
    board = Board()
    board.reset()
    led = Led(board, "led1", "PA5")
    btn = Button(board, "btn1", "PA0", active_high=True)
    board.devices.update(led1=led, btn1=btn)
    board.core.load_segments(fw_exti_button().build())
    sim = Simulation(board)
    sim.schedule(5_000_000, btn.press)          # 5ms 时按下
    rep = sim.run(until_ms=15, wall_timeout_s=10)
    edges = [e for e in board.events.query("gpio.PA5") if e.t_ns > 1_000_000]
    assert len(edges) >= 1, "按键未触发 PA5 翻转"
    t0 = edges[0].t_ns
    assert 4_900_000 <= t0 <= 5_200_000, f"翻转时刻 {t0/1e6:.3f}ms 未跟随按键 5ms"
    assert rep.exceptions >= 1


def test_m3_nvic_disable_blocks_irq():
    """ISER 使能位清零 → EXTI pending 但不进入。"""
    board = Board()
    board.reset()
    led = Led(board, "led1", "PA5")
    btn = Button(board, "btn1", "PA0")
    board.devices.update(led1=led, btn1=btn)
    board.core.load_segments(fw_exti_button().build())
    sim = Simulation(board)
    sim.schedule(2_000_000, lambda: board.sysctrl._iser.__setitem__(0, 0))   # 固件初始化后再禁能
    sim.schedule(4_000_000, btn.press)
    sim.run(until_ms=8, wall_timeout_s=10)
    toggles = [e for e in board.events.query("gpio.PA5") if e.t_ns > 1_000_000]
    assert len(toggles) == 0
    assert board.sysctrl.is_pending(22)


def fw_preemption() -> Firmware:
    """SysTick(优先级0) 抢占 EXTI0(优先级5)：EXTI 处理期间 SysTick 能进来。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, 5); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010800)
    a.mov32(1, crlh({1: 0x2, 4: 0x2, 5: 0x2})); a.str(1, 0, 0)
    a.mov32(0, 0x40010400); a.movs(1, 1); a.str(1, 0, 0); a.str(1, 0, 8)
    # EXTI0 优先级 = 5（IPR0 高 nibble）
    a.mov32(0, 0xE000E400)
    a.movs(1, 5 << 4); a.strb(1, 0, 6)   # EXTI0=IRQ6 -> IPR 字节6
    # SysTick 优先级 = 0（SHPR3 byte2 @0xE000ED22）
    a.mov32(0, 0xE000ED20)
    a.movs(1, 0); a.strb(1, 0, 2)
    # 使能 EXTI0
    a.mov32(0, 0xE000E100); a.mov32(1, 1 << 6); a.str(1, 0, 0)
    # SysTick 1ms
    a.mov32(0, 0xE000E010)
    a.movw(1, 7999); a.str(1, 0, 4); a.movs(1, 0); a.str(1, 0, 8)
    a.movs(1, 7); a.str(1, 0, 0)
    a.label("idle")
    a.wfi(); a.bw("idle")

    # EXTI0 handler：翻转 PA4，忙等 ~2ms，再清 PR —— 期间应被 SysTick 抢占
    h = Asm(0x08000180)
    h.mov32(0, 0x4001080C)
    h.ldr(1, 0, 0); h.movs(2, 0x10); h.eor(1, 2); h.str(1, 0, 0)
    h.mov32(3, 16000)                          # 忙等计数
    h.label("wait")
    h.subs(3, 1)
    h.bne("wait")
    h.mov32(0, 0x40010414); h.movs(1, 1); h.str(1, 0, 0)
    h.bx_lr()

    # SysTick handler：翻转 PA1
    st = Asm(0x08000200)
    st.mov32(0, 0x4001080C)
    st.ldr(1, 0, 0); st.movs(2, 0x02); st.eor(1, 2); st.str(1, 0, 0)
    st.bx_lr()

    fw.add(0x08000100, a.assemble())
    fw.add(0x08000180, h.assemble())
    fw.add(0x08000200, st.assemble())
    fw.vector(22, 0x08000180)
    fw.vector(15, 0x08000200)
    return fw


def test_m3_preemption_fires():
    """构造：4ms 时按键 → EXTI0(prio5) handler 忙等 2ms；期间 SysTick(prio0) 每毫秒抢占翻转 PA1。"""
    from zetsim.engine import Simulation as Sim
    board = Board()
    board.reset()
    fw = fw_preemption()
    board.core.load_segments(fw.build())
    btn = Button(board, "btn1", "PA0")
    board.devices["btn1"] = btn
    sim = Sim(board)
    sim.schedule(4_000_000, btn.press)
    rep = sim.run(until_ms=8, wall_timeout_s=20)
    pa1 = [e for e in board.events.query("gpio.PA1") if e.t_ns > 1_000_000]
    pa4 = [e for e in board.events.query("gpio.PA4") if e.t_ns > 1_000_000]
    assert len(pa4) >= 1, "EXTI0 未进入"
    # EXTI handler 从 4ms 忙等至 ~6ms；SysTick 在 5ms、6ms 抢占 → PA1 至少翻转 1 次
    assert len(pa1) >= 1, "SysTick 未能在低优先级 handler 期间抢占"
    # 抢占发生在 EXTI handler 窗口 (4ms, 6.5ms) 内
    preempt_ts = [e.t_ns for e in pa1 if 4_000_000 < e.t_ns < 6_500_000]
    assert preempt_ts, "抢占时间不在 EXTI handler 窗口内"


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
