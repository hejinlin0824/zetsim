from __future__ import annotations

import json
from pathlib import Path

import pytest

from zetsim.soc_specs import _load_soc_spec, get_soc_spec, soc_catalog

ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = ROOT / "zetsim" / "data" / "soc" / "esp32s3.json"


def test_esp32s3_soc_spec_keeps_chip_facts_separate_from_runtime_fidelity():
    spec = get_soc_spec("esp32s3")
    assert spec["architecture"]["isa"] == "Xtensa LX7"
    assert spec["architecture"]["cores"] == 2
    assert spec["gpio"]["programmable_count"] == 45
    assert spec["gpio"]["valid_gpio_numbers"] == [[0, 21], [26, 48]]
    assert [item["gpio"] for item in spec["gpio"]["strap_pins"]] == [0, 3, 45, 46]
    assert spec["peripherals"]["uart"]["count"] == 3
    assert spec["peripherals"]["led_pwm"]["channels_up_to"] == 8
    assert spec["fidelity"]["runtime_implemented"] is False
    json.dumps(spec)


def test_soc_catalog_is_versioned_and_only_lists_supported_targets():
    specs = soc_catalog()
    assert [item["target"] for item in specs] == ["esp32s3"]
    assert specs[0]["sources"]["technical_reference_manual"]["version"] == "1.8"


def test_soc_spec_rejects_invalid_gpio_ranges(tmp_path: Path):
    spec = json.loads(SPEC_FILE.read_text(encoding="utf-8"))
    spec["gpio"]["valid_gpio_numbers"] = [[0, 21], [20, 48]]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(ValueError, match="重复号码"):
        _load_soc_spec(path)
