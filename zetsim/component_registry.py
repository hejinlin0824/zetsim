"""Declarative component registry shared by schematic validation and UI tooling."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

COMPONENTS: dict[str, dict[str, Any]] = {
    "mcu": {"label": "STM32 MCU", "category": "controller",
        "pins": ["P" + port + str(bit) for port in "ABCDE" for bit in range(16)] + ["VDD", "VSS"],
        "renderer": "mcu", "capabilities": ["digital", "gpio"], "properties": {}},
    "esp32s3": {"label": "ESP32-S3", "category": "controller",
        "pins": ["3V3", "GND", "EN", "TX", "RX"] + ["GPIO" + str(i) for i in range(49)],
        "renderer": "esp32s3", "capabilities": ["digital", "gpio", "uart"], "properties": {}},
    "led": {"label": "LED", "category": "output", "pins": ["A", "K"], "renderer": "led",
        "capabilities": ["digital", "analog"],
        "properties": {"color": {"type": "string", "default": "red"}, "vf": {"type": "number", "default": 2.0}}},
    "resistor": {"label": "Resistor", "category": "passive", "pins": ["1", "2"], "renderer": "resistor",
        "capabilities": ["analog"], "properties": {"ohms": {"type": "number", "default": 1000.0, "min": 0.000001}}},
    "capacitor": {"label": "Capacitor", "category": "passive", "pins": ["1", "2"], "renderer": "capacitor",
        "capabilities": ["analog"], "properties": {"farads": {"type": "number", "default": 1e-7, "min": 1e-15}}},
    "button": {"label": "Push button", "category": "input", "pins": ["1", "2"], "renderer": "button",
        "capabilities": ["digital", "interactive"],
        "properties": {"debounce_ms": {"type": "number", "default": 0.0, "min": 0, "max": 1000}}},
    "pot": {"label": "Potentiometer", "category": "input", "pins": ["W", "B"], "renderer": "pot",
        "capabilities": ["analog", "interactive"], "properties": {}},
    "gnd": {"label": "Ground", "category": "power", "pins": ["G"], "renderer": "ground", "capabilities": ["power"], "properties": {}},
    "vcc": {"label": "3.3V power", "category": "power", "pins": ["V"], "renderer": "vcc", "capabilities": ["power"], "properties": {}},
    "probe": {"label": "Voltage probe", "category": "instrument", "pins": ["P"], "renderer": "probe", "capabilities": ["observe"], "properties": {}},
}

def component_pin_defs() -> dict[str, list[str]]:
    """Return a fresh legacy-compatible mapping of component type to pin names."""
    return {kind: list(spec["pins"]) for kind, spec in COMPONENTS.items()}

def component_catalog() -> list[dict[str, Any]]:
    """Return JSON-friendly, defensive copies for APIs and front-end tooling."""
    return [{"type": kind, **deepcopy(spec)} for kind, spec in COMPONENTS.items()]

def get_component(kind: str) -> dict[str, Any]:
    try:
        return deepcopy(COMPONENTS[kind])
    except KeyError as exc:
        raise ValueError(f"不支持的元件类型：{kind}") from exc
