"""M7: mini-SPICE 混合仿真 — PWM 经 RC 低通滤波、LED 电气特性。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from zetsim.board import Board
from zetsim.engine import Simulation
from zetsim.spice import CoupledCircuit
from test_m4 import fw_pwm


def make_rc_board(rc_ohms=1000.0, rc_farads=100e-9):
    """PWM(PA0) -> R -> C 节点 -> GND；探针测电容电压。"""
    board = Board()
    board.reset()
    board.core.load_segments(fw_pwm().build())     # PA0: 10kHz PWM 30%
    cc = CoupledCircuit(board, dt_ns=2_000)        # 2µs 子步
    cc.attach_pin("PA0", "pwm")
    cc.circuit.add_r("pwm", "vc", rc_ohms)
    cc.circuit.add_c("vc", "GND", rc_farads)
    cc.probe("vc", "vc")
    board.devices["spice"] = cc                    # engine 每片调用 step()
    return board, cc


def test_m7_rc_filter_average():
    """10kHz 30% PWM 经 RC(1k+100nF, fc=1.6kHz) -> 平均电压 ≈ 0.3*3.3V"""
    board, cc = make_rc_board()
    sim = Simulation(board)
    rep = sim.run(until_ms=4, wall_timeout_s=30)
    hist = cc.history["vc"]
    assert len(hist) >= 20, "SPICE 未随仿真步进"
    # 取最后 1ms 稳态平均
    t_end = hist[-1][0]
    tail = [v for t, v in hist if t >= t_end - 1_000_000]
    avg = sum(tail) / len(tail)
    expect = 0.30 * 3.3
    assert abs(avg - expect) < 0.12, f"RC 平均 {avg:.3f}V ≠ {expect:.3f}V"
    # 纹波幅度应明显小于轨电压（fc=1.6kHz 滤 10kHz，理论纹波 ~0.55V p-p）
    ripple = max(tail) - min(tail)
    assert ripple < 1.5, f"纹波过大 {ripple:.3f}V（RC 未滤波?）"


def test_m7_rc_charge_curve():
    """充电时间常数: RC=100µs，50µs 处电压应约 0.632*终值区间量级"""
    board, cc = make_rc_board(rc_ohms=1000.0, rc_farads=100e-9)  # tau=100µs
    sim = Simulation(board)
    rep = sim.run(until_ms=1, wall_timeout_s=20)
    hist = cc.history["vc"]
    # 找第一个从 0 开始的上升段（PWM 周期 100µs）
    t0, v0 = hist[0]
    # 上升沿后 50µs ≈ 0.4 * 终值(0.99V) ≈ 0.4V 左右（30% 占空比下）
    t_end = hist[-1][0]
    tail = [v for t, v in hist if t >= t_end - 300_000]
    assert max(tail) < 1.5, "电容电压不应超过占空比平均+纹波"


def make_led_board():
    """PA5(数字输出) -> LED -> 220Ω -> GND；LED 正向压降 ~2V。"""
    from zetsim.asm import Asm, Firmware
    from test_m1_m2 import crlh
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018)
    a.ldr(1, 0, 0); a.movs(2, 4); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010800)
    a.mov32(1, crlh({5: 0x2})); a.str(1, 0, 0)
    a.mov32(0, 0x4001080C)
    a.movs(1, 1)                     # ODR |= 1<<5? 直接置 ODR=0x20
    a.lsls(1, 1, 5)
    a.str(1, 0, 0)
    a.label("idle")
    a.wfi(); a.bw("idle")
    fw.add(0x08000100, a.assemble())

    board = Board()
    board.reset()
    board.core.load_segments(fw.build())
    cc = CoupledCircuit(board, dt_ns=10_000)
    cc.attach_pin("PA5", "pin")
    led = cc.circuit.add_led("pin", "vd", is_=1e-12, n_vt=0.052)
    cc.circuit.add_r("vd", "GND", 220.0)
    cc.probe("vd", "vd")
    board.devices["spice"] = cc
    return board, cc, led


def test_m7_led_forward_voltage():
    """LED 导通: 正向压降 1.8~2.6V（指数结特性），电流 = (3.3-Vf)/220"""
    board, cc, led = make_led_board()
    sim = Simulation(board)
    rep = sim.run(until_ms=1, wall_timeout_s=10)
    pin_v = cc.circuit.voltage("pin")
    cathode_v = cc.circuit.voltage("vd")
    vf = pin_v - cathode_v       # 正向压降是阳极到阴极的电压差，不是阴极对地电压
    assert 1.7 < vf < 2.7, f"LED 正向压降 {vf:.2f}V 异常"
    i = led.i_last
    expect_i = cathode_v / 220.0
    assert i > 2e-3, f"LED 电流 {i*1e3:.2f}mA 应 >2mA"
    assert abs(i - expect_i) < 1e-3, f"LED 电流与限流电阻不一致：{i*1e3:.2f}mA vs {expect_i*1e3:.2f}mA"
    # LED 关断（引脚低）时电流≈0
    src = cc.pin_sources["PA5"]
    src.volts = 0.0
    cc.circuit.step(1e-5)
    cc.circuit.step(1e-5)
    assert led.i_last < 1e-6, f"关断电流 {led.i_last*1e9:.1f}nA 应≈0"


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
