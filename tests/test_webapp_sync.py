from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from zetsim.webapp import build_app


def _valid_circuit() -> dict:
    return {
        "components": [
            {"id": "MCU", "type": "mcu", "x": 20, "y": 20, "props": {}},
            {"id": "VCC1", "type": "vcc", "x": 0, "y": 0, "props": {}},
            {"id": "GND1", "type": "gnd", "x": 0, "y": 100, "props": {}},
            {"id": "LED1", "type": "led", "x": 100, "y": 20, "props": {}},
            {"id": "SW1", "type": "button", "x": 100, "y": 100, "props": {}},
            {"id": "POT1", "type": "pot", "x": 100, "y": 180, "props": {}},
        ],
        "wires": [
            {"a": ["MCU", "VDD"], "b": ["VCC1", "V"]},
            {"a": ["MCU", "VSS"], "b": ["GND1", "G"]},
            {"a": ["MCU", "PA5"], "b": ["LED1", "A"]},
            {"a": ["LED1", "K"], "b": ["GND1", "G"]},
            {"a": ["MCU", "PA0"], "b": ["SW1", "1"]},
            {"a": ["SW1", "2"], "b": ["GND1", "G"]},
            {"a": ["MCU", "PA1"], "b": ["POT1", "W"]},
            {"a": ["POT1", "B"], "b": ["GND1", "G"]},
        ],
    }


def test_schematic_api_rejects_invalid_circuit_without_corrupting_active_state():
    with TestClient(build_app()) as client:
        valid = _valid_circuit()
        response = client.post("/api/schematic", json=valid)
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["snapshot"]["mcu_powered"] is True
        assert "LED1" in response.json()["snapshot"]["leds"]

        invalid = deepcopy(valid)
        invalid["wires"].append(
            {"a": ["MCU", "PA99"], "b": ["LED1", "A"]}
        )
        rejected = client.post("/api/schematic", json=invalid)
        assert rejected.status_code == 400
        assert "PA99" in rejected.json()["error"]

        state = client.get("/api/state").json()
        assert state["mcu_powered"] is True
        assert "LED1" in state["leds"]
        assert state["buttons"]["SW1"] is False


def test_component_api_serializes_valid_controls_and_rejects_missing_components():
    with TestClient(build_app()) as client:
        valid = _valid_circuit()
        response = client.post("/api/schematic", json=valid)
        assert response.status_code == 200

        pressed = client.post("/api/comp/SW1/press", json={})
        assert pressed.status_code == 200
        assert pressed.json()["ok"] is True
        assert client.get("/api/state").json()["buttons"]["SW1"] is True

        released = client.post("/api/comp/SW1/release", json={})
        assert released.status_code == 200
        assert client.get("/api/state").json()["buttons"]["SW1"] is False

        missing = client.post("/api/comp/DOES_NOT_EXIST/press", json={})
        assert missing.status_code == 404
        assert missing.json()["ok"] is False


def test_component_api_rejects_non_finite_potentiometer_input():
    with TestClient(build_app()) as client:
        response = client.post("/api/schematic", json=_valid_circuit())
        assert response.status_code == 200

        invalid = client.post(
            "/api/comp/POT1/pot",
            content='{"volts": NaN}',
            headers={"Content-Type": "application/json"},
        )
        assert invalid.status_code == 400
        assert "有限数" in invalid.json()["error"]



def test_monaco_workbench_docks_live_schematic_and_runtime_controls() -> None:
    """The project workspace keeps the real schematic/debug panels beside code."""
    html = (Path(__file__).resolve().parents[1] / "zetsim" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    required = (
        "monaco-editor@0.52.2/min/vs/loader.js",
        'id="monacoHost"',
        'id="projPreviewGrid"',
        "function openProjectWorkbench()",
        "function closeProjectWorkbench()",
        "function activateMonacoFile(file)",
        "monaco.editor.create(host",
        'id="projRunBtn"',
        'id="projPauseBtn"',
        'id="projResetBtn"',
        "fetch('/api/project/'+proj.name+'/build'",
        "function dockProjectPreview()",
        "function undockProjectPreview()",
    )
    missing = [item for item in required if item not in html]
    assert not missing, f"missing live code/schematic workbench features: {missing}"
    assert ".editorWrap.monaco-ready #projCode{display:none!important}" in html
    assert "兼容编辑器 · Monaco CDN 加载失败" in html


def test_component_and_target_catalog_apis_are_explicit_and_scoped():
    with TestClient(build_app()) as client:
        components = client.get("/api/components")
        assert components.status_code == 200
        ids = {item["type"] for item in components.json()["items"]}
        assert {"mcu", "led", "resistor", "capacitor", "button", "pot", "gnd", "vcc", "probe"} <= ids
        targets = client.get("/api/targets")
        assert {item["id"] for item in targets.json()["items"]} == {"stm32f103zet6", "esp32s3"}


def test_versioned_project_snapshot_export_import_and_rejection_are_safe():
    with TestClient(build_app()) as client:
        exported = client.get("/api/project/snapshot")
        assert exported.status_code == 200
        project = exported.json()
        assert project["schema_version"] == 1
        assert project["target"] == "stm32f103zet6"
        assert "components" in project["circuit"]

        imported = client.post("/api/project/snapshot", json=project)
        assert imported.status_code == 200
        assert imported.json()["ok"] is True

        before = client.get("/api/state").json()
        invalid = dict(project)
        invalid["target"] = "avr-uno"
        rejected = client.post("/api/project/snapshot", json=invalid)
        assert rejected.status_code == 400
        after = client.get("/api/state").json()
        assert before["mcu_powered"] == after["mcu_powered"]
        assert set(before["leds"]) == set(after["leds"])

        unsupported = dict(project)
        unsupported["target"] = "esp32s3"
        response = client.post("/api/project/snapshot", json=unsupported)
        assert response.status_code == 400



def test_board_catalog_api_exposes_esp32s3_board_without_mutating_stm32_registry():
    with TestClient(build_app()) as client:
        response = client.get("/api/boards")
        assert response.status_code == 200
        items = response.json()["items"]
        assert [board["id"] for board in items] == ["esp32-s3-devkitc-1"]
        board = items[0]
        assert board["target"] == "esp32s3"
        assert board["pins"]["TX"]["gpio"] == 43
        assert board["pins"]["RX"]["gpio"] == 44
        assert board["leds"][1]["type"] == "ws2812"
        # The legacy MCU component is still the STM32 pin model.
        components = client.get("/api/components").json()["items"]
        mcu = next(item for item in components if item["type"] == "mcu")
        assert "PA5" in mcu["pins"]
        assert all(not pin.startswith("GPIO") for pin in mcu["pins"])
