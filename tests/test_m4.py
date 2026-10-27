"""M4: TIM2 PWM 频率/占空比 + ADC 采样电位器 + 示波器。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from zetsim.asm import Asm, Firmware
from zetsim.board import Board
from zetsim.engine import Simulation
from zetsim.devices import Potentiometer, Oscilloscope
from test_m1_m2 import crlh


def fw_pwm() -> Firmware:
    """TIM2 CH1 (PA0) PWM: psc=7 arr=99 ccr1=30 -> 10kHz @30%（HSI 8MHz）"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    # RCC: APB1ENR |= TIM2(0), APB2ENR |= GPIOA(2)
    a.mov32(0, 0x4002101C)
    a.ldr(1, 0, 0); a.movs(2, 1); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, 4); a.orr(1, 2); a.str(1, 0, 0)
    # PA0 = AF 推挽 50MHz (0xB)
    a.mov32(0, 0x40010800)
    a.mov32(1, crlh({0: 0xB})); a.str(1, 0, 0)
    # TIM2 base 0x40000000
    a.mov32(0, 0x40000000)
    a.movw(1, 7); a.str(1, 0, 0x28)                    # PSC
    a.movw(1, 99); a.str(1, 0, 0x2C)                   # ARR
    a.movw(1, 30); a.str(1, 0, 0x34)                   # CCR1
    a.movw(1, 0x60); a.str(1, 0, 0x18)                 # CCMR1: OC1M=110 PWM1
    a.movw(1, 1); a.str(1, 0, 0x20)                    # CCER: CC1E
    a.movw(1, 1); a.str(1, 0, 0x00)                    # CR1: CEN
    a.label("idle")
    a.wfi(); a.bw("idle")
    fw.add(0x08000100, a.assemble())
    return fw


def test_m4_pwm_frequency_and_duty():
    board = Board()
    board.reset()
    scope = Oscilloscope(board, "scope1", ["PA0"])
    board.devices["scope1"] = scope
    board.core.load_segments(fw_pwm().build())
    sim = Simulation(board)
    rep = sim.run(until_ms=5, wall_timeout_s=15)

    f = scope.measure_frequency("PA0", t0_ns=500_000)
    duty = scope.measure_duty("PA0", t0_ns=500_000)
    assert f is not None, "无 PWM 边沿"
    assert abs(f - 10_000) / 10_000 < 0.05, f"PWM 频率 {f:.1f} Hz ≠ 10kHz"
    assert duty is not None and abs(duty - 0.30) < 0.03, f"占空比 {duty:.3f} ≠ 30%"


def fw_adc() -> Firmware:
    """ADC1 通道1(PA1) 软件启动单次转换，轮询 EOC 读 DR 后 bkpt。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, (1 << 9) | (1 << 2)); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40012400)                 # ADC1
    a.movw(1, 1); a.str(1, 0, 0x34)        # SQR3: 通道1
    a.movs(1, 1); a.str(1, 0, 0x08)        # CR2: ADON=1 上电
    a.mov32(1, 1 << 30 | 1)
    a.str(1, 0, 0x08)                      # CR2: SWSTART|ADON
    a.label("wait")
    a.ldr(1, 0, 0)                         # SR
    a.lsrs(1, 1, 1)
    a.lsls(1, 1, 31)
    a.bpl("wait")                          # EOC==0 等待
    a.ldr(2, 0, 0x4C)                      # DR
    a.bkpt()
    fw.add(0x08000100, a.assemble())
    return fw


def test_m4_adc_pot():
    board = Board()
    board.reset()
    pot = Potentiometer(board, "pot1", "PA1", volts=2.5)
    board.devices["pot1"] = pot
    board.core.load_segments(fw_adc().build())
    sim = Simulation(board)
    rep = sim.run(until_ms=5, wall_timeout_s=10)
    expect = 2.5 / 3.3 * 4095
    got = board.adcs[1].regs.get(0x4C, -1)
    assert rep.halt_reason == "bkpt"
    assert abs(got - expect) < 30, f"ADC 值 {got} ≠ {expect:.0f} (2.5V)"


def test_m4_adc_tracks_pot_change():
    """连续转换模式下改电位器，DR 跟随。"""
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, (1 << 9) | (1 << 2)); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40012400)
    a.movw(1, 1); a.str(1, 0, 0x34)
    a.movs(1, 3); a.str(1, 0, 0x08)                 # ADON|CONT
    a.mov32(1, (1 << 30) | 3); a.str(1, 0, 0x08)    # SWSTART|ADON|CONT
    a.label("idle")
    a.wfi(); a.bw("idle")
    fw.add(0x08000100, a.assemble())

    board = Board()
    board.reset()
    pot = Potentiometer(board, "pot1", "PA1", volts=0.8)
    board.devices["pot1"] = pot
    board.core.load_segments(fw.build())
    sim = Simulation(board)
    sim.schedule(1_000_000, lambda: pot.set(2.0))
    sim.run(until_ms=3, wall_timeout_s=10)
    adc = board.adcs[1]
    hist = []
    v_final = adc._sample(1)
    expect_final = 2.0 / 3.3 * 4095
    assert abs(v_final - expect_final) < 30, f"连续转换未跟随电位器: {v_final} vs {expect_final:.0f}"


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
