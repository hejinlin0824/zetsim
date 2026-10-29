"""Read-only catalog for versioned hardware-register metadata.

This module does not implement MMIO behaviour. Consumers must check the
fidelity fields before making simulation claims.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REGISTER_DIR = Path(__file__).resolve().parent / "data" / "registers"


def _load_register_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取寄存器元数据 {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"寄存器元数据 {path} 必须是 JSON 对象")
    if payload.get("schema_version") != 1:
        raise ValueError(f"不支持的寄存器元数据版本：{payload.get('schema_version')}")
    if payload.get("target") != "esp32s3":
        raise ValueError(f"当前首版寄存器目录只允许 esp32s3，实际为 {payload.get('target')!r}")
    if not isinstance(payload.get("peripheral"), str) or not payload["peripheral"]:
        raise ValueError("peripheral 必须是非空字符串")
    expected_base = {"gpio": "DR_REG_GPIO_BASE", "io_mux": "DR_REG_IO_MUX_BASE"}.get(payload["peripheral"])
    if expected_base is None or payload.get("base_symbol") != expected_base or payload.get("base_address") is not None:
        raise ValueError("寄存器元数据必须使用已登记的基地址符号，不得填未经确认的绝对地址")
    if payload.get("fidelity") != "metadata-only" or payload.get("runtime_implemented") is not False:
        raise ValueError("仅有元数据的寄存器目录必须明确标记 metadata-only / runtime_implemented=false")
    registers = payload.get("registers")
    if not isinstance(registers, list) or not registers:
        raise ValueError("registers 必须是非空数组")
    seen_names: set[str] = set()
    seen_offsets: set[int] = set()
    normalized = []
    for item in registers:
        if not isinstance(item, dict):
            raise ValueError("每个寄存器条目必须是对象")
        name, offset, access = item.get("name"), item.get("offset"), item.get("access")
        if not isinstance(name, str) or not name or name in seen_names:
            raise ValueError(f"寄存器名称无效或重复：{name!r}")
        if not isinstance(offset, str):
            raise ValueError(f"寄存器 {name} 的 offset 必须是十六进制字符串")
        try:
            offset_value = int(offset, 16)
        except ValueError as exc:
            raise ValueError(f"寄存器 {name} 的 offset 无效：{offset!r}") from exc
        if offset_value < 0 or offset_value % 4:
            raise ValueError(f"寄存器 {name} 的 offset 必须非负且按 4 字节对齐")
        if offset_value in seen_offsets:
            raise ValueError(f"寄存器偏移重复：{offset}")
        if access not in {"RO", "RW", "WO"}:
            raise ValueError(f"寄存器 {name} 的 access 不支持：{access!r}")
        if item.get("offset_value") != offset_value:
            raise ValueError(f"寄存器 {name} 的 offset_value 与 offset 不一致")
        seen_names.add(name)
        seen_offsets.add(offset_value)
        normalized.append(dict(item))
    return {**payload, "registers": normalized}


def register_catalog() -> list[dict[str, Any]]:
    """Load and validate all locally bundled register metadata catalogues."""
    if not _REGISTER_DIR.is_dir():
        return []
    return [_load_register_file(path) for path in sorted(_REGISTER_DIR.glob("*.json"))]


def get_register_catalog(peripheral: str) -> dict[str, Any]:
    for item in register_catalog():
        if item["peripheral"] == peripheral:
            return item
    raise ValueError(f"不存在寄存器目录：{peripheral}")
