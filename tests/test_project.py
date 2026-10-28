from __future__ import annotations
import pytest
from zetsim.project import dump_project, from_legacy_circuit, load_project, new_project, to_legacy_circuit, validate_project
from zetsim.targets import get_target

def test_project_round_trip_and_legacy_adapter(tmp_path):
    circuit = {"components": [
        {"id": "MCU", "type": "mcu", "x": 1, "y": 2, "props": {}},
        {"id": "LED1", "type": "led", "x": 3, "y": 4, "props": {"color": "green"}}],
        "wires": [{"a": ["MCU", "PA5"], "b": ["LED1", "A"]}]}
    project = from_legacy_circuit(circuit, name="test")
    assert project["schema_version"] == 1
    assert project["target"] == "stm32f103zet6"
    assert to_legacy_circuit(project) == circuit
    path = tmp_path / "zetsim.json"
    dump_project(project, path)
    assert load_project(path) == project

def test_project_rejects_unknown_target_and_bad_wire_pin():
    with pytest.raises(ValueError, match="不支持的目标"):
        new_project(target="avr-uno")
    project = new_project(components=[
        {"id": "MCU", "type": "mcu", "x": 0, "y": 0, "props": {}},
        {"id": "LED1", "type": "led", "x": 0, "y": 0, "props": {}}],
        wires=[{"a": ["MCU", "PA99"], "b": ["LED1", "A"]}])
    with pytest.raises(ValueError, match="不存在引脚"):
        validate_project(project)

def test_project_rejects_future_schema_and_non_text_files():
    with pytest.raises(ValueError, match="格式版本"):
        validate_project({"schema_version": 99})
    with pytest.raises(ValueError, match="files"):
        validate_project({"files": {"main.c": 42}})

def test_only_two_product_targets_are_registered():
    from zetsim.targets import TARGETS
    assert set(TARGETS) == {"stm32f103zet6", "esp32s3"}
    assert get_target("ESP32S3")["backend"] == "espressif-qemu"
