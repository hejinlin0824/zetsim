"""M8: 原理图网表 —— 画电路即仿真。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from zetsim.board import Board
from zetsim.engine import Simulation
from zetsim.schematic import Schematic


def sch(comps, wires):
    """构造原理图；含 MCU 时自动补电源（VDD→3.3V，VSS→GND）。"""
    if any(c["type"] == "mcu" for c in comps) and not any(
            w[1] == "VDD" or w[3] == "VDD" for w in
            ([w["a"][0], w["a"][1], w["b"][0], w["b"][1]] for w in wires)):
        comps = comps + [{"id": "PWR1", "type": "vcc", "x": 230, "y": -80, "props": {}},
                         {"id": "GNDP", "type": "gnd", "x": 230, "y": 930, "props": {}}]
        wires = wires + [{"a": ["PWR1", "V"], "b": ["MCU", "VDD"]},
                         {"a": ["MCU", "VSS"], "b": ["GNDP", "G"]}]
    return {"components": comps, "wires": wires}


def test_mcu_needs_power():
    """不给 MCU 供电：CPU 不执行指令、引脚高阻 LED 不亮；接上电源立即恢复。"""
    from zetsim.schematic import PIN_DEFS
    board = Board()
    board.reset()
    s = Schematic(board)
    board.devices["schematic"] = s
    base = [
        {"id": "MCU", "type": "mcu", "x": 60, "y": 60, "props": {}},
        {"id": "LED1", "type": "led", "x": 400, "y": 200, "props": {}},
        {"id": "G1", "type": "gnd", "x": 560, "y": 222, "props": {}},
    ]
    wires = [{"a": ["MCU", "PA5"], "b": ["LED1", "A"]},
             {"a": ["LED1", "K"], "b": ["G1", "G"]}]
    board.core.load_segments(_blink_fw().build())
    # 无电源
    s.apply({"components": base, "wires": wires})
    sim = Simulation(board)
    rep = sim.run(until_ms=30, wall_timeout_s=10)
    assert s.mcu_powered is False
    assert rep.instructions < 100, "掉电时 CPU 不应执行指令"
    assert s.led_states()["LED1"]["on"] is False, "掉电时 LED 不亮"
    # 接上电源 → 恢复运行
    s.apply(sch(base, wires))
    assert s.mcu_powered is True
    sim.run(until_ms=400, wall_timeout_s=10)
    assert s.led_states()["LED1"]["on"] is True, "供电后应恢复跑灯"


def _blink_fw():
    from zetsim.asm import Firmware, Asm
    from tests.test_m1_m2 import crlh
    fw = Firmware(sp=0x20005000, reset=0x08000100)
    a = Asm(0x08000100)
    a.mov32(0, 0x40021018); a.ldr(1, 0, 0); a.movs(2, 5); a.orr(1, 2); a.str(1, 0, 0)
    a.mov32(0, 0x40010800); a.mov32(1, crlh({5: 0x2})); a.str(1, 0, 0)
    a.mov32(0, 0x4001080C); a.movs(1, 0x20); a.str(1, 0, 0)
    a.label("loop"); a.bw("loop")
    fw.add(0x08000100, a.assemble())
    return fw


MCU = {"id": "MCU", "type": "mcu", "x": 0, "y": 0, "props": {}}


def test_netlist_union_find():
    board = Board(); board.reset()
    s = Schematic(board)
    s.apply(sch(
        [MCU,
         {"id": "LED1", "type": "led", "x": 0, "y": 0, "props": {}},
         {"id": "G1", "type": "gnd", "x": 0, "y": 0, "props": {}}],
        [{"a": ["MCU", "PA5"], "b": ["LED1", "A"]},
         {"a": ["LED1", "K"], "b": ["G1", "G"]}],
    ))
    assert s.pin_net[("MCU", "PA5")] == s.pin_net[("LED1", "A")]
    assert s.pin_net[("LED1", "K")] != s.pin_net[("MCU", "PA5")]
    assert s.mcu_pin_nets["PA5"] == s.pin_net[("MCU", "PA5")]


def test_led_direct_digital():
    """MCU.PA5 - LED - GND：直接数字驱动。"""
    board = Board(); board.reset()
    s = Schematic(board)
    s.apply(sch(
        [MCU,
         {"id": "LED1", "type": "led", "x": 0, "y": 0, "props": {}},
         {"id": "G1", "type": "gnd", "x": 0, "y": 0, "props": {}}],
        [{"a": ["MCU", "PA5"], "b": ["LED1", "A"]},
         {"a": ["LED1", "K"], "b": ["G1", "G"]}],
    ))
    g = board.gpios[0]
    g.write(0x00, 4, 0x00200000)      # CRL: PA5 输出
    g.write(0x0C, 4, 0x20)            # ODR = 1<<5
    assert s.led_states()["LED1"]["on"] is True
    g.write(0x0C, 4, 0)
    assert s.led_states()["LED1"]["on"] is False


def test_led_series_resistor_spice():
    """MCU.PA5 - 220R - LED - GND：结点电压/电流由 SPICE 解。"""
    board = Board(); board.reset()
    s = Schematic(board)
    s.apply(sch(
        [MCU,
         {"id": "R1", "type": "resistor", "x": 0, "y": 0, "props": {"ohms": 220}},
         {"id": "LED1", "type": "led", "x": 0, "y": 0, "props": {}},
         {"id": "G1", "type": "gnd", "x": 0, "y": 0, "props": {}}],
        [{"a": ["MCU", "PA5"], "b": ["R1", "1"]},
         {"a": ["R1", "2"], "b": ["LED1", "A"]},
         {"a": ["LED1", "K"], "b": ["G1", "G"]}],
    ))
    assert s.spice is not None, "含 R 应触发 SPICE"
    g = board.gpios[0]
    g.write(0x00, 4, 0x00200000)
    g.write(0x0C, 4, 0x20)            # PA5 = 3.3V
    for _ in range(30):
        s.spice.step(1e-6)
    d = s._spice_leds["LED1"]
    i = abs(d.i_last)
    assert 2e-3 < i < 20e-3, f"LED 电流 {i*1e3:.2f}mA 异常"
    assert s.led_states()["LED1"]["on"] is True
    g.write(0x0C, 4, 0)
    for _ in range(30):
        s.spice.step(1e-6)
    assert abs(d.i_last) < 1e-6
    assert s.led_states()["LED1"]["on"] is False


def test_button_exti_via_schematic():
    """原理图接按键到 PA0 -> button_exti.hex -> 按键触发中断翻转 PA5。"""
    board = Board(); board.reset()
    s = Schematic(board)
    board.devices["schematic"] = s
    s.apply(sch(
        [MCU,
         {"id": "SW1", "type": "button", "x": 0, "y": 0, "props": {}},
         {"id": "LED1", "type": "led", "x": 0, "y": 0, "props": {}},
         {"id": "G1", "type": "gnd", "x": 0, "y": 0, "props": {}},
         {"id": "G2", "type": "gnd", "x": 0, "y": 0, "props": {}}],
        [{"a": ["MCU", "PA0"], "b": ["SW1", "1"]},
         {"a": ["SW1", "2"], "b": ["G1", "G"]},
         {"a": ["MCU", "PA5"], "b": ["LED1", "A"]},
         {"a": ["LED1", "K"], "b": ["G2", "G"]}],
    ))
    board.core.load_file("firmware/button_exti.hex")
    sim = Simulation(board)
    sim.schedule(4_000_000, lambda: s.press("SW1", True))
    sim.schedule(4_500_000, lambda: s.press("SW1", False))
    rep = sim.run(until_ms=10, wall_timeout_s=15)
    edges = [e for e in board.events.query("gpio.PA5") if e.t_ns > 1_000_000]
    assert len(edges) >= 1, f"原理图按键未触发中断翻转: {len(edges)}"
    assert 3_900_000 <= edges[0].t_ns <= 5_000_000
    assert rep.exceptions >= 1


def test_rc_probe_via_schematic():
    """PWM(PA0) - 1k - 100n - GND，探针在结点：RC 滤波平均 ~= 0.99V。"""
    board = Board(); board.reset()
    s = Schematic(board)
    board.devices["schematic"] = s
    s.apply(sch(
        [MCU,
         {"id": "R1", "type": "resistor", "x": 0, "y": 0, "props": {"ohms": 1000}},
         {"id": "C1", "type": "capacitor", "x": 0, "y": 0, "props": {"farads": 100e-9}},
         {"id": "G1", "type": "gnd", "x": 0, "y": 0, "props": {}},
         {"id": "PR1", "type": "probe", "x": 0, "y": 0, "props": {}}],
        [{"a": ["MCU", "PA0"], "b": ["R1", "1"]},
         {"a": ["R1", "2"], "b": ["C1", "1"]},
         {"a": ["C1", "2"], "b": ["G1", "G"]},
         {"a": ["R1", "2"], "b": ["PR1", "P"]}],
    ))
    board.core.load_file("firmware/pwm_adc.hex")
    sim = Simulation(board)
    rep = sim.run(until_ms=4, wall_timeout_s=30)
    tr = s.probes["PR1"].trace
    assert len(tr) >= 20, f"探针轨迹过少: {len(tr)}"
    t_end = tr[-1][0]
    tail = [v for t, v in tr if t >= t_end - 1_000_000]
    avg = sum(tail) / len(tail)
    assert abs(avg - 0.99) < 0.15, f"RC 平均 {avg:.3f}V != 0.99V"
    assert max(tail) - min(tail) < 1.5, "纹波过大"
