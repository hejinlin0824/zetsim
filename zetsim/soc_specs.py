"""Versioned SoC specification registry, separate from boards and runtime models."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .targets import TARGETS

_SPEC_DIR = Path(__file__).resolve().parent / "data" / "soc"


def _load_soc_spec(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 SoC 规格数据 {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("SoC 规格数据必须是 JSON 对象")
    if payload.get("schema_version") != 1:
        raise ValueError(f"不支持的 SoC 规格版本：{payload.get('schema_version')}")
    target = payload.get("target")
    if target not in TARGETS:
        raise ValueError(f"SoC 规格引用了不支持的目标：{target!r}")
    if not isinstance(payload.get("name"), str) or not payload["name"]:
        raise ValueError("SoC 规格缺少 name")
    architecture = payload.get("architecture")
    if not isinstance(architecture, dict) or not isinstance(architecture.get("isa"), str) or not architecture["isa"]:
        raise ValueError("architecture 必须声明非空 isa")
    gpio = payload.get("gpio")
    if not isinstance(gpio, dict) or gpio.get("programmable_count") != 45:
        raise ValueError("ESP32-S3 GPIO 规格必须声明 45 个可编程 GPIO")
    ranges = gpio.get("valid_gpio_numbers")
    if not isinstance(ranges, list) or not ranges:
        raise ValueError("valid_gpio_numbers 必须是非空范围数组")
    flattened: set[int] = set()
    for item in ranges:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("GPIO 范围必须是 [start, end]")
        start, end = item
        if any(isinstance(value, bool) or not isinstance(value, int) for value in item) or start < 0 or end < start:
            raise ValueError(f"无效 GPIO 范围：{item!r}")
        for number in range(start, end + 1):
            if number in flattened:
                raise ValueError(f"GPIO 范围存在重复号码：{number}")
            flattened.add(number)
    strap = gpio.get("strap_pins")
    if not isinstance(strap, list):
        raise ValueError("strap_pins 必须是数组")
    seen_straps: set[int] = set()
    for item in strap:
        if not isinstance(item, dict) or isinstance(item.get("gpio"), bool) or not isinstance(item.get("gpio"), int):
            raise ValueError("strap_pins 中每项必须声明整数 gpio")
        pin = item["gpio"]
        if pin not in flattened or pin in seen_straps:
            raise ValueError(f"启动配置引脚无效或重复：GPIO{pin}")
        if not isinstance(item.get("roles"), list) or any(not isinstance(role, str) for role in item["roles"]):
            raise ValueError(f"GPIO{pin} 的 roles 必须是字符串数组")
        seen_straps.add(pin)
    peripherals = payload.get("peripherals")
    if not isinstance(peripherals, dict) or not peripherals:
        raise ValueError("peripherals 必须是对象")
    fidelity = payload.get("fidelity")
    if not isinstance(fidelity, dict) or fidelity.get("runtime_implemented") is not False:
        raise ValueError("SoC 文档规格必须明确为非运行时实现")
    sources = payload.get("sources")
    if not isinstance(sources, dict) or not sources.get("datasheet") or not sources.get("technical_reference_manual"):
        raise ValueError("SoC 规格必须记录数据手册和技术参考手册来源")
    return payload


def soc_catalog() -> list[dict[str, Any]]:
    """Return all versioned SoC specifications as defensive JSON values."""
    if not _SPEC_DIR.is_dir():
        return []
    return [_load_soc_spec(path) for path in sorted(_SPEC_DIR.glob("*.json"))]


def get_soc_spec(target: str) -> dict[str, Any]:
    for spec in soc_catalog():
        if spec["target"] == target:
            return spec
    raise ValueError(f"没有 SoC 规格：{target}")
