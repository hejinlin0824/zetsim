from __future__ import annotations

from copy import deepcopy

import pytest

from zetsim.board import Board
from zetsim.schematic import Schematic
from zetsim.spice import Capacitor


def _base_schematic(*, isolated_probe: bool = False) -> dict:
    components = [
        {"id": "MCU", "type": "mcu", "x": 0, "y": 0, "props": {}},
        {"id": "VCC1", "type": "vcc", "x": 0, "y": -20, "props": {}},
        {"id": "GND1", "type": "gnd", "x": 0, "y": 20, "props": {}},
        {"id": "R1", "type": "resistor", "x": 100, "y": 0, "props": {"ohms": 1000}},
        {"id": "C1", "type": "capacitor", "x": 150, "y": 0, "props": {"farads": 1e-7}},
        {"id": "SW1", "type": "button", "x": 200, "y": 0, "props": {}},
        {"id": "POT1", "type": "pot", "x": 250, "y": 0, "props": {}},
        {"id": "PR1", "type": "probe", "x": 300, "y": 0, "props": {}},
    ]
    wires = [
        {"a": ["MCU", "VDD"], "b": ["VCC1", "V"]},
        {"a": ["MCU", "VSS"], "b": ["GND1", "G"]},
        {"a": ["MCU", "PA5"], "b": ["R1", "1"]},
        {"a": ["R1", "2"], "b": ["C1", "1"]},
        {"a": ["C1", "2"], "b": ["GND1", "G"]},
        {"a": ["MCU", "PA0"], "b": ["SW1", "1"]},
        {"a": ["SW1", "2"], "b": ["GND1", "G"]},
        {"a": ["MCU", "PA1"], "b": ["POT1", "W"]},
        {"a": ["POT1", "B"], "b": ["GND1", "G"]},
        {"a": ["MCU", "PA7"], "b": ["PR1", "P"]},
        # Two MCU pins on the same schematic net must resolve to the same runtime Net.
        {"a": ["MCU", "PA5"], "b": ["MCU", "PA6"]},
    ]
    if isolated_probe:
        components.append({"id": "PR2", "type": "probe", "x": 350, "y": 0, "props": {}})
    return {"components": components, "wires": wires}


def test_connected_mcu_pins_share_runtime_net_for_gpio_reads_and_writes():
    board = Board()
    schematic = Schematic(board)
    data = {
        "components": [
            {"id": "MCU", "type": "mcu", "x": 0, "y": 0, "props": {}},
            {"id": "VCC1", "type": "vcc", "x": 0, "y": -20, "props": {}},
            {"id": "GND1", "type": "gnd", "x": 0, "y": 20, "props": {}},
        ],
        "wires": [
            {"a": ["MCU", "VDD"], "b": ["VCC1", "V"]},
            {"a": ["MCU", "VSS"], "b": ["GND1", "G"]},
            {"a": ["MCU", "PA5"], "b": ["MCU", "PA6"]},
        ],
    }
    schematic.apply(data)

    board.set_mcu_output(0, 5, 1)
    assert board.read_input(0, 6) == 1
    board.set_mcu_output(0, 6, 0)
    assert board.read_input(0, 5) == 0


def test_removed_probe_is_removed_and_isolated_probe_falls_back_from_spice():
    board = Board()
    schematic = Schematic(board)
    data = _base_schematic(isolated_probe=True)
    schematic.apply(data)
    assert set(schematic.probes) == {"PR1", "PR2"}
    assert schematic.spice is not None
    # Only GPIOs connected to analog/interactive circuit elements should enter the MNA solver.
    assert set(schematic.spice.pin_sources) == {"PA0", "PA5"}

    isolated_net_id = schematic.probes["PR2"].net_id
    # PR2 is not connected to any SPICE element; sampling it must not raise KeyError.
    assert isinstance(schematic.net_voltage(isolated_net_id), float)

    data["components"] = [c for c in data["components"] if c["id"] != "PR2"]
    schematic.apply(data)
    assert set(schematic.probes) == {"PR1"}
    assert "PR2" not in schematic.snapshot()["probes"]


def test_invalid_schematic_is_rejected_before_active_circuit_is_replaced():
    board = Board()
    schematic = Schematic(board)
    valid = _base_schematic()
    schematic.apply(valid)
    before = deepcopy(schematic.data)

    invalid = deepcopy(valid)
    invalid["wires"].append({"a": ["MCU", "PA99"], "b": ["R1", "1"]})
    with pytest.raises(ValueError, match="引脚"):
        schematic.apply(invalid)

    assert schematic.data == before
    assert "SW1" in schematic.buttons
    assert schematic.spice is not None


def test_button_and_pot_updates_keep_spice_transient_state():
    board = Board()
    schematic = Schematic(board)
    schematic.apply(_base_schematic())

    coupled = schematic.spice
    assert coupled is not None
    capacitor = next(comp for comp in coupled.circuit.comps if isinstance(comp, Capacitor))
    capacitor.vprev = 1.234
    button_resistor = schematic._spice_buttons["SW1"]

    assert schematic.press("SW1", True) is True
    assert button_resistor.r == pytest.approx(10.0)
    assert schematic.set_pot("POT1", 2.7) is True
    assert schematic.board.resolved_net(0, 1).voltage() == pytest.approx(2.7)

    assert schematic.spice is coupled
    assert capacitor.vprev == pytest.approx(1.234)
    assert schematic.press("SW1", False) is True
    assert button_resistor.r == pytest.approx(10e6)


def test_invalid_runtime_component_actions_are_not_silently_accepted():
    schematic = Schematic(Board())
    schematic.apply(_base_schematic())
    assert schematic.press("DOES_NOT_EXIST", True) is False
    assert schematic.set_pot("DOES_NOT_EXIST", 1.2) is False
    with pytest.raises(ValueError, match="有限数"):
        schematic.set_pot("POT1", float("nan"))

def test_spice_fixed_step_accumulates_elapsed_time_without_speeding_up():
    from zetsim.spice import CoupledCircuit

    board = Board()
    coupled = CoupledCircuit(board, dt_ns=5_000)

    class CountingCircuit:
        def __init__(self):
            self.steps = 0

        def step(self, _dt):
            self.steps += 1

        def voltage(self, _name):
            return 0.0

    counter = CountingCircuit()
    coupled.circuit = counter
    coupled.enabled = True

    coupled.step(3_000)
    assert counter.steps == 0
    assert coupled._remainder_ns == 3_000

    coupled.step(5_000)
    assert counter.steps == 1
    assert coupled._remainder_ns == 0

    coupled.step(7_000)
    assert counter.steps == 1
    assert coupled._remainder_ns == 2_000

    coupled.step(10_000)
    assert counter.steps == 2
    assert coupled._remainder_ns == 0


def test_gpio_spice_source_has_finite_output_impedance():
    from zetsim.spice import CoupledCircuit, Resistor, VoltageSource

    board = Board()
    coupled = CoupledCircuit(board)
    rail = coupled.circuit.add_source("VCC_TEST", "GND")
    rail.volts = 3.3
    source = coupled.attach_pin("PA5", "VCC_TEST")

    assert source.n1.name == "__gpio_drive_PA5"
    assert any(
        isinstance(comp, Resistor)
        and {comp.n1.name, comp.n2.name} == {"__gpio_drive_PA5", "VCC_TEST"}
        and comp.r == pytest.approx(25.0)
        for comp in coupled.circuit.comps
    )
    coupled.circuit.step(5e-6)
    assert all(abs(value) < float("inf") for value in coupled.circuit._last)
    assert coupled.circuit.voltage("VCC_TEST") == pytest.approx(3.3)

def test_spice_rebases_after_simulation_clock_is_reset():
    from zetsim.spice import CoupledCircuit

    board = Board()
    coupled = CoupledCircuit(board, dt_ns=5_000)

    class CountingCircuit:
        def __init__(self):
            self.steps = 0

        def step(self, _dt):
            self.steps += 1

        def voltage(self, _name):
            return 0.0

    counter = CountingCircuit()
    coupled.circuit = counter
    coupled.enabled = True

    coupled.step(5_000)
    coupled.step(8_000)
    assert counter.steps == 1
    assert coupled._remainder_ns == 3_000

    # Firmware load resets SysTick/engine time to zero; the solver must not carry a negative-time gap.
    coupled.step(0)
    assert coupled._last_ns == 0
    assert coupled._remainder_ns == 0
    assert counter.steps == 1

    coupled.step(5_000)
    assert counter.steps == 2

def test_vcc_only_spice_circuit_runs_and_duplicate_rails_are_deduplicated():
    board = Board()
    schematic = Schematic(board)
    schematic.apply({
        "components": [
            {"id": "VCC1", "type": "vcc", "x": 0, "y": 0, "props": {}},
            {"id": "VCC2", "type": "vcc", "x": 0, "y": 30, "props": {}},
            {"id": "GND1", "type": "gnd", "x": 0, "y": 100, "props": {}},
            {"id": "R1", "type": "resistor", "x": 100, "y": 0, "props": {"ohms": 1000}},
        ],
        "wires": [
            {"a": ["VCC1", "V"], "b": ["R1", "1"]},
            {"a": ["VCC2", "V"], "b": ["R1", "1"]},
            {"a": ["R1", "2"], "b": ["GND1", "G"]},
        ],
    })

    assert schematic.spice is not None
    assert schematic.spice.enabled is True
    assert len(schematic.spice.circuit.sources) == 1
    root = schematic.pin_net[("R1", "1")]
    node = schematic._node_of_net[root]
    schematic.spice.step(board.sysctrl.now_ns + schematic.spice.dt_ns)
    assert schematic.spice.stepped is True
    assert schematic.spice.circuit.voltage(node) == pytest.approx(3.3)

