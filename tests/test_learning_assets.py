"""Regression tests for safe, teachable starter schematics."""
from __future__ import annotations

from zetsim.webapp import DEFAULT_SCHEMATIC, _led8_schematic


def _wire_pairs(schematic: dict) -> set[frozenset[tuple[str, str]]]:
    return {
        frozenset((tuple(wire["a"]), tuple(wire["b"])))
        for wire in schematic["wires"]
    }


def _wire(a: tuple[str, str], b: tuple[str, str]) -> frozenset[tuple[str, str]]:
    return frozenset((a, b))


def test_default_led_path_includes_current_limiting_resistor() -> None:
    schematic = DEFAULT_SCHEMATIC
    components = {component["id"]: component for component in schematic["components"]}
    wires = _wire_pairs(schematic)

    assert components["R_LED1"]["type"] == "resistor"
    assert components["R_LED1"]["props"]["ohms"] == 330
    assert _wire(("MCU", "PA5"), ("R_LED1", "1")) in wires
    assert _wire(("R_LED1", "2"), ("LED1", "A")) in wires
    assert _wire(("LED1", "K"), ("GND1", "G")) in wires
    assert _wire(("MCU", "PA5"), ("LED1", "A")) not in wires


def test_every_led_marquee_output_has_a_330_ohm_series_resistor() -> None:
    schematic = _led8_schematic()
    components = {component["id"]: component for component in schematic["components"]}
    wires = _wire_pairs(schematic)

    for index in range(8):
        resistor_id = f"R{index + 1}"
        led_id = f"LED{index + 1}"
        ground_id = f"GND{index + 1}"
        pin = f"PA{index}"

        assert components[resistor_id]["type"] == "resistor"
        assert components[resistor_id]["props"]["ohms"] == 330
        assert _wire(("MCU", pin), (resistor_id, "1")) in wires
        assert _wire((resistor_id, "2"), (led_id, "A")) in wires
        assert _wire((led_id, "K"), (ground_id, "G")) in wires
        assert _wire(("MCU", pin), (led_id, "A")) not in wires
