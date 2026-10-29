from __future__ import annotations

import json
from pathlib import Path

import pytest

from zetsim.registers import get_register_catalog, register_catalog


ROOT = Path(__file__).resolve().parents[1]
REGISTER_FILE = ROOT / "zetsim" / "data" / "registers" / "esp32s3-gpio.json"


def test_esp32s3_gpio_register_catalog_is_documented_but_not_claimed_implemented():
    catalog = get_register_catalog("gpio")
    assert catalog["target"] == "esp32s3"
    assert catalog["source"]["version"] == "1.8"
    assert catalog["source"]["section"].startswith("6.14.1")
    assert catalog["fidelity"] == "metadata-only"
    assert catalog["runtime_implemented"] is False
    regs = {item["name"]: item for item in catalog["registers"]}
    assert regs["GPIO_OUT_REG"]["offset"] == "0x0004"
    assert regs["GPIO_OUT_W1TS_REG"]["offset"] == "0x0008"
    assert regs["GPIO_OUT_W1TS_REG"]["access"] == "WO"
    assert "sets" in regs["GPIO_OUT_W1TS_REG"]["side_effect"]
    assert regs["GPIO_OUT_W1TC_REG"]["access"] == "WO"
    assert regs["GPIO_STRAP_REG"]["access"] == "RO"
    assert regs["GPIO_IN1_REG"]["offset"] == "0x0040"
    json.dumps(catalog)


def test_register_catalog_has_unique_aligned_offsets_and_known_access_modes():
    catalog = register_catalog()
    assert [item["peripheral"] for item in catalog] == ["gpio"]
    regs = catalog[0]["registers"]
    offsets = [item["offset_value"] for item in regs]
    assert len(offsets) == len(set(offsets))
    assert all(offset >= 0 and offset % 4 == 0 for offset in offsets)
    assert {item["access"] for item in regs} <= {"RO", "RW", "WO"}


def test_register_catalog_rejects_claiming_metadata_as_runtime_implementation(tmp_path: Path):
    payload = json.loads(REGISTER_FILE.read_text(encoding="utf-8"))
    payload["runtime_implemented"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    from zetsim.registers import _load_register_file
    with pytest.raises(ValueError, match="metadata-only"):
        _load_register_file(path)
