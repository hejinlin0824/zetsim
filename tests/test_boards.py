from __future__ import annotations

import json
from pathlib import Path

import pytest

from zetsim.boards import board_catalog, get_board, load_board, validate_board


ROOT = Path(__file__).resolve().parents[1]
BOARD_FILE = ROOT / "zetsim" / "data" / "boards" / "esp32-s3-devkitc-1.json"


def test_esp32s3_devkitc_board_registry_contains_header_aliases_and_onboard_leds():
    board = get_board("esp32-s3-devkitc-1")
    assert board.target == "esp32s3"
    assert board.mcu == "esp32-s3"
    assert board.width_mm == pytest.approx(25.527)
    assert board.height_mm == pytest.approx(70.057)
    assert board.pins["TX"].gpio == 43
    assert board.pins["TX"].x_mm == pytest.approx(24.19)
    assert board.pins["TX"].y_mm == pytest.approx(10.207)
    assert board.pins["RX"].gpio == 44
    assert board.pins["38"].gpio == 38
    assert board.pins["RST"].kind == "reset"
    assert board.pins["5V"].voltage == 5.0
    assert board.pins["GND.1"].kind == "ground"
    assert "strapping" in board.pins["0"].constraints
    assert "uart0-default-tx" in board.pins["TX"].constraints
    assert board.leds[1]["type"] == "ws2812"
    assert board.leds[1]["pins"]["DI"] == "38"


def test_board_catalog_is_json_friendly_and_keeps_supported_target_scope():
    catalog = board_catalog()
    assert [item["id"] for item in catalog] == ["esp32-s3-devkitc-1"]
    assert catalog[0]["target"] == "esp32s3"
    assert len(catalog[0]["headers"]["left"]) == 22
    assert len(catalog[0]["headers"]["right"]) == 22
    assert catalog[0]["dimensions_mm"] == {"width": 25.527, "height": 70.057}
    assert catalog[0]["pins"]["38"]["x_mm"] is not None
    assert catalog[0]["leds"][1]["x"] == pytest.approx(7.45)
    json.dumps(catalog)


def test_board_loader_accepts_comments_without_corrupting_urls_or_strings(tmp_path: Path):
    path = tmp_path / "demo.json"
    path.write_text(
        '// board comment\n'
        '{"id":"demo","name":"Demo","mcu":"esp32-s3","target":"esp32s3",'
        '"pins":{"TX":{"target":"GPIO43"},"P":{"target":"power(3.3)"}},'
        '"metadata":{"source":"https://example.invalid/a//b"}}\n'
        '/* trailing comment */\n',
        encoding="utf-8",
    )
    board = load_board(path)
    assert board.pins["TX"].gpio == 43
    assert board.metadata["source"] == "https://example.invalid/a//b"


def test_board_loader_rejects_unknown_target_and_invalid_header_references():
    base = {
        "id": "demo", "name": "Demo", "mcu": "esp32-s3", "target": "avr",
        "pins": {"1": {"target": "GPIO1"}},
    }
    with pytest.raises(ValueError, match="不支持的目标"):
        validate_board(base)
    base["target"] = "esp32s3"
    base["headers"] = {"left": ["MISSING"]}
    with pytest.raises(ValueError, match="不存在的引脚"):
        validate_board(base)


def test_board_loader_rejects_non_finite_pin_coordinates(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(
        '{"id":"bad","name":"Bad","mcu":"esp32-s3","target":"esp32s3",'
        '"pins":{"1":{"target":"GPIO1","x":NaN,"y":10}}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="有限数字"):
        load_board(path)



def test_board_loader_rejects_coordinates_outside_declared_dimensions():
    payload = json.loads(BOARD_FILE.read_text(encoding="utf-8"))
    payload["pins"]["TX"]["x"] = payload["width_mm"] + 1
    with pytest.raises(ValueError, match="超出板卡尺寸"):
        validate_board(payload)
