from __future__ import annotations

import pytest

from zetsim.board import Board
from zetsim.periph.adc import Adc
from zetsim.schematic import Schematic
from zetsim.spice import Circuit


def _mcu_pin_schematic(*, top_ohms: float = 2000.0, bottom_ohms: float = 10_000.0) -> dict:
    return {
        "components": [
            {"id": "MCU", "type": "mcu", "x": 0, "y": 0, "props": {}},
            {"id": "VCC1", "type": "vcc", "x": 0, "y": -30, "props": {}},
            {"id": "GND1", "type": "gnd", "x": 0, "y": 100, "props": {}},
            {"id": "R_TOP", "type": "resistor", "x": 100, "y": 0, "props": {"ohms": top_ohms}},
            {"id": "R_BOTTOM", "type": "resistor", "x": 200, "y": 0, "props": {"ohms": bottom_ohms}},
        ],
        "wires": [
            {"a": ["MCU", "VDD"], "b": ["VCC1", "V"]},
            {"a": ["MCU", "VSS"], "b": ["GND1", "G"]},
            {"a": ["VCC1", "V"], "b": ["R_TOP", "1"]},
            {"a": ["R_TOP", "2"], "b": ["R_BOTTOM", "1"]},
            {"a": ["R_TOP", "2"], "b": ["MCU", "PA1"]},
            {"a": ["R_BOTTOM", "2"], "b": ["GND1", "G"]},
        ],
    }


def test_gpio_floating_input_and_internal_pull_up_pull_down():
    board = Board()
    board.reset()
    gpio = board.gpios[0]
    net = board.net(0, 0)

    # Reset state is a floating input; the deterministic digital read policy is low.
    assert net.level is None
    assert gpio.read(0x08, 4) & 1 == 0

    # PA0: MODE=00, CNF=10 => input pull-up/down; ODR selects pull-down.
    crl_pull = (0x44444444 & ~0xF) | 0x8
    gpio.write(0x00, 4, crl_pull)
    assert net.level == 0
    assert gpio.read(0x08, 4) & 1 == 0

    # ODR=1 selects pull-up without changing CRL.
    gpio.write(0x0C, 4, 1)
    assert net.level == 1
    assert gpio.read(0x08, 4) & 1 == 1

    # ODR=0 returns to pull-down.
    gpio.write(0x0C, 4, 0)
    assert net.level == 0

    # Switching to floating input removes the internal pull.
    gpio.write(0x00, 4, 0x44444444)
    assert net.level is None
    assert gpio.read(0x08, 4) & 1 == 0


def test_gpio_open_drain_releases_line_and_push_pull_overrides_external_level():
    board = Board()
    board.reset()
    gpio = board.gpios[0]
    net = board.net(0, 0)

    # PA0: MODE=11, CNF=01 => general-purpose open-drain output.
    gpio.write(0x00, 4, (0x44444444 & ~0xF) | 0x7)
    net.set_device(1)  # external pull-up / externally driven high
    assert net.level == 0  # ODR reset value 0 actively sinks the line

    gpio.write(0x0C, 4, 1)  # open-drain high = release, not an active high drive
    assert net.level == 1

    net.set_device(None)
    assert net.level is None  # released line without an external pull-up floats

    # Push-pull drives both high and low regardless of an opposing external digital level.
    gpio.write(0x00, 4, (0x44444444 & ~0xF) | 0x3)
    net.set_device(0)
    gpio.write(0x0C, 4, 1)
    assert net.level == 1
    gpio.write(0x0C, 4, 0)
    assert net.level == 0


def test_shared_net_keeps_independent_pin_drivers_and_flags_contention():
    board = Board()
    schematic = Schematic(board)
    schematic.apply({
        "components": [
            {"id": "MCU", "type": "mcu", "x": 0, "y": 0, "props": {}},
            {"id": "VCC1", "type": "vcc", "x": 0, "y": -20, "props": {}},
            {"id": "GND1", "type": "gnd", "x": 0, "y": 20, "props": {}},
        ],
        "wires": [
            {"a": ["MCU", "VDD"], "b": ["VCC1", "V"]},
            {"a": ["MCU", "VSS"], "b": ["GND1", "G"]},
            {"a": ["MCU", "PA0"], "b": ["MCU", "PA1"]},
        ],
    })
    gpio = board.gpios[0]
    # PA0 push-pull output, PA1 floating input. Reconfiguring PA1 must not clear PA0's driver.
    gpio.write(0x00, 4, 0x44444443)
    gpio.write(0x0C, 4, 1)
    assert board.resolved_net(0, 0) is board.resolved_net(0, 1)
    assert gpio.read(0x08, 4) & 0b11 == 0b11

    # If both connected pins actively drive opposite levels, the digital network is undefined.
    gpio.write(0x00, 4, 0x44444433)
    gpio.write(0x0C, 4, 0b01)
    assert board.resolved_net(0, 0).level is None
    gpio.write(0x0C, 4, 0b11)
    assert board.resolved_net(0, 0).level == 1


def test_adc_reads_solved_resistor_divider_voltage_instead_of_gpio_default_zero():
    board = Board()
    schematic = Schematic(board)
    schematic.apply(_mcu_pin_schematic(top_ohms=2000.0, bottom_ohms=10_000.0))

    # PA1 must be an analog input; the SPICE GPIO source must therefore be high impedance.
    board.gpios[0].write(0x00, 4, 0x44444404)
    assert schematic.spice is not None
    assert schematic.spice.pin_resistors["PA1"].r == pytest.approx(1e12)

    schematic.spice.step(board.sysctrl.now_ns + schematic.spice.dt_ns)
    voltage = schematic.mcu_pin_voltage("PA1")
    assert voltage == pytest.approx(2.75, abs=0.02)

    adc = board.adcs[1]
    adc.regs[0x34] = 1  # ADC channel 1 = PA1
    adc.regs[0x08] = 1  # ADON
    adc._complete()
    expected = round(2.75 / 3.3 * 4095)
    assert adc.regs[0x4C] == pytest.approx(expected, abs=30)
    assert board.read_input(0, 1) == 1  # the solved voltage is above the approximate VIH threshold


def test_adc_clamps_out_of_range_and_non_finite_voltages():
    board = Board()
    adc = board.adcs[1]
    net = board.net(0, 0)

    net.device_analog = 4.5
    assert adc._sample(0) == 4095

    net.device_analog = -1.0
    assert adc._sample(0) == 0

    net.device_analog = float("nan")
    assert adc._sample(0) == 0


def test_configurable_button_debounce_rejects_short_bounce_and_accepts_stable_press():
    board = Board()
    schematic = Schematic(board)
    schematic.apply({
        "components": [
            {"id": "SW1", "type": "button", "x": 0, "y": 0, "props": {"debounce_ms": 5}},
        ],
        "wires": [],
    })
    button = schematic.buttons["SW1"]
    assert button.pressed is False

    # A 1ms press followed by release is shorter than the 5ms stable window.
    board.sysctrl.now_ns = 1_000_000
    assert schematic.press("SW1", True)
    board.sysctrl.now_ns = 2_000_000
    assert schematic.press("SW1", False)
    schematic.sample(7_000_000)
    assert button.pressed is False
    assert not schematic.button_pending

    # A press that stays stable for 5ms is accepted only at the end of the window.
    board.sysctrl.now_ns = 10_000_000
    assert schematic.press("SW1", True)
    schematic.sample(14_999_999)
    assert button.pressed is False
    schematic.sample(15_000_000)
    assert button.pressed is True
    assert schematic.snapshot()["buttons"]["SW1"] is True


@pytest.mark.parametrize("debounce_ms", [-0.1, float("nan"), 1000.1])
def test_schematic_rejects_invalid_button_debounce_values(debounce_ms):
    schematic = Schematic(Board())
    with pytest.raises(ValueError, match="消抖时间"):
        schematic.apply({
            "components": [
                {"id": "SW1", "type": "button", "x": 0, "y": 0, "props": {"debounce_ms": debounce_ms}},
            ],
            "wires": [],
        })


def test_rc_step_response_matches_first_order_time_constant():
    circuit = Circuit()
    supply = circuit.add_source("VCC", "GND")
    supply.volts = 3.3
    circuit.add_r("VCC", "VC", 1000.0)
    capacitor = circuit.add_c("VC", "GND", 100e-9)  # tau = 100 us

    for _ in range(100):
        circuit.step(1e-6)

    # Backward Euler is slightly dissipative, but should be close to 63.2% after one tau.
    voltage = circuit.voltage("VC")
    assert voltage == pytest.approx(3.3 * (1.0 - (1.0 / 1.01) ** 100), abs=0.03)
    assert capacitor.vprev == pytest.approx(voltage, abs=1e-9)

def test_spice_gpio_open_drain_uses_external_pullup_when_released():
    from zetsim.spice import CoupledCircuit

    board = Board()
    board.reset()
    coupled = CoupledCircuit(board, dt_ns=5_000)
    rail = coupled.circuit.add_source("VCC", "GND")
    rail.volts = 3.3
    coupled.attach_pin("PA0", "PIN")
    coupled.circuit.add_r("PIN", "VCC", 10_000.0)

    gpio = board.gpios[0]
    gpio.write(0x00, 4, (0x44444444 & ~0xF) | 0x7)  # general open-drain
    gpio.write(0x0C, 4, 1)  # release the line
    assert coupled.pin_resistors["PA0"].r == pytest.approx(1e12)
    coupled.step(5_000)
    assert coupled.circuit.voltage("PIN") == pytest.approx(3.3, abs=0.01)

    gpio.write(0x0C, 4, 0)  # sink low
    coupled.step(10_000)
    assert coupled.pin_resistors["PA0"].r == pytest.approx(25.0)
    assert coupled.circuit.voltage("PIN") < 0.02


def test_spice_models_internal_pullup_as_weak_resistance():
    from zetsim.spice import CoupledCircuit

    board = Board()
    board.reset()
    coupled = CoupledCircuit(board, dt_ns=5_000)
    rail = coupled.circuit.add_source("VCC", "GND")
    rail.volts = 3.3
    coupled.circuit.add_r("PIN", "GND", 100_000.0)
    coupled.attach_pin("PA0", "PIN")

    gpio = board.gpios[0]
    gpio.write(0x00, 4, (0x44444444 & ~0xF) | 0x8)  # input pull-up/down
    gpio.write(0x0C, 4, 1)  # ODR=1 selects pull-up
    assert coupled.pin_resistors["PA0"].r == pytest.approx(40_000.0)
    coupled.step(5_000)

    # Nominal 40k pull-up into a 100k pull-down: V = 3.3 * 100k / 140k.
    assert coupled.circuit.voltage("PIN") == pytest.approx(3.3 * 100_000 / 140_000, abs=0.03)

