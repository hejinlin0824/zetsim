"""M1: USART1 发送 "Hello, zetsim!"  M2: SysTick 异常引擎 + LED 闪烁 + WFI 快进。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from zetsim.asm import Asm, Firmware
from zetsim.board import Board
from zetsim.engine import Simulation
from zetsim.devices import Led


# ---------------- M1 固件：串口 Hello ----------------
def crlh(values: dict[int, int], default: int = 0x4) -> int:
    """按引脚号拼 CRL/CRH 半字配置：crlh({5: 0x2}) → PA5=0x2 其余 0x4。"""
    v = 0
    for pin in range(16):
        nib = values.get(pin, default)
        v |= nib << (pin * 4)
    return v


def fw_hello() -> Firmware:
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # RCC_APB2ENR |= USART1(14) | GPIOA(2)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0)
    a.movs(2, 0x40); a.lsls(2, 2, 8)          # 0x4000
    a.movs(3, 4); a.orr(2, 3)                 # | 4
    a.orr(1, 2)
    a.str(1, 0, 0)
    # GPIOA_CRH = PA9 AF推挽50M (0xB)
    a.mov32(0, 0x40010804)
    a.mov32(1, crlh({9: 0xB}))
    a.str(1, 0, 0)
    # USART1: BRR(8MHz/115200≈69.44→0x457), CR1=UE|TE
    a.mov32(0, 0x40013800)
    a.movw(1, 0x0457); a.str(1, 0, 8)
    a.movw(1, 0x2008); a.str(1, 0, 0x0C)
    # 发送
    a.mov32(2, 0x08000200)                      # msg 指针
    a.label("next")
    a.ldr(1, 0, 0)                              # SR
    a.lsrs(1, 1, 7)
    a.lsls(1, 1, 31)
    a.b("next", "pl")                            # TXE==0 等待
    a.ldrb(3, 2, 0)
    a.cmp(3, 0)
    a.beq("done")
    a.str(3, 0, 4)                              # DR
    a.adds(2, 1)
    a.b("next")
    a.label("done")
    a.bkpt()
    msg = Asm(0x08000200)
    msg.asciz("Hello, zetsim!\r\n")
    fw.add(0x08000100, a.assemble())
    fw.add(0x08000200, msg.assemble())
    return fw


def test_m1_usart_hello():
    board = Board()
    board.reset()
    board.core.load_segments(fw_hello().build())
    sim = Simulation(board)
    rep = sim.run(until_ms=10)
    tx = [e.data for e in board.events.query("usart1.tx")]
    text = bytes(tx).decode("ascii", "replace")
    assert text == "Hello, zetsim!\r\n", f"uart got {text!r}"
    assert rep.halt_reason == "bkpt"
    assert rep.instructions > 50


def test_m1_baud_from_brr():
    board = Board()
    u = board.usarts[1]
    u.regs[0x08] = 0x457        # 69+7/16
    # HSI 8MHz, APB2 不分频
    assert abs(u.baud_hz() - 8_000_000 / 69.4375) < 1


# ---------------- M2 固件：SysTick 1ms 翻转 PA5 ----------------
def fw_systick_blink() -> Firmware:
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # RCC APB2ENR |= GPIOA(2)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0)
    a.movs(2, 4); a.orr(1, 2); a.str(1, 0, 0)
    # GPIOA_CRL: PA5 输出推挽 2MHz (0x2)
    a.mov32(0, 0x40010800)
    a.mov32(1, crlh({5: 0x2}))
    a.str(1, 0, 0)
    # SysTick: LOAD=7999 (1ms @8MHz), VAL=0, CTRL=7
    a.mov32(0, 0xE000E010)
    a.movw(1, 7999); a.str(1, 0, 4)
    a.movs(1, 0); a.str(1, 0, 8)
    a.movs(1, 7); a.str(1, 0, 0)
    # 主循环：wfi
    a.label("idle")
    a.wfi()
    a.bw("idle")
    # --- SysTick_Handler @ 0x08000180 ---
    h = Asm(0x08000180)
    h.mov32(0, 0x4001080C)      # GPIOA_ODR
    h.ldr(1, 0, 0)
    h.movs(2, 0x20)
    h.eor(1, 2)
    h.str(1, 0, 0)
    h.bx_lr()
    fw.add(0x08000100, a.assemble())
    fw.add(0x08000180, h.assemble())
    fw.vector(15, 0x08000180)   # SysTick
    return fw


def test_m2_systick_blink_exception_engine():
    """异常引擎期末考第一关：SysTick 中断进出栈 + LED 翻转 + 频率精确。"""
    board = Board()
    board.reset()
    led = Led(board, "led1", "PA5")
    board.devices["led1"] = led
    board.core.load_segments(fw_systick_blink().build())
    sim = Simulation(board)
    rep = sim.run(until_ms=50)

    edges = board.events.query("gpio.PA5")
    assert len(edges) >= 40, f"翻转次数不足: {len(edges)}"
    # 频率 = 1kHz ±10%（周期 1ms）
    ts = [e.t_ns for e in edges]
    periods = [ts[i + 1] - ts[i] for i in range(1, len(ts) - 1)]
    assert periods
    periods.sort()
    med = periods[len(periods) // 2]
    assert 900_000 <= med <= 1_100_000, f"中位周期 {med} ns 不符"
    assert rep.exceptions >= 40
    # LED 状态与最后一个电平一致
    assert led.on == bool(edges[-1].data)


def test_m2_wfi_fastforward_is_fast():
    """WFI 快进：50ms 仿真含 50 次中断，指令数应远小于忙等。"""
    import time
    board = Board()
    board.reset()
    board.core.load_segments(fw_systick_blink().build())
    sim = Simulation(board)
    t0 = time.time()
    rep = sim.run(until_ms=50, wall_timeout_s=30)
    dt = time.time() - t0
    assert rep.halt_reason == "timeout"
    assert dt < 10, f"WFI 快进失效，耗时 {dt:.1f}s"
    # 忙等 50ms@8MHz/cpi2 = 200k 条；快进下应只有几万条（每 tick 少量指令）
    assert rep.instructions < 60_000, f"指令数 {rep.instructions} 暗示未快进"


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
