"""Versioned JSON project format and backwards-compatible circuit adapter."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from typing import Any
from .component_registry import COMPONENTS
from .targets import TARGETS

SCHEMA_VERSION = 1
DEFAULT_TARGET = "stm32f103zet6"
PROJECT_FILE = "zetsim.json"

def new_project(*, name: str = "Untitled", target: str = DEFAULT_TARGET,
                files: dict[str, str] | None = None,
                components: list[dict] | None = None, wires: list[dict] | None = None) -> dict[str, Any]:
    get_target_id(target)
    return {"schema_version": SCHEMA_VERSION, "name": name, "target": target.lower(),
            "files": deepcopy(files or {}),
            "circuit": {"components": deepcopy(components or []), "wires": deepcopy(wires or [])},
            "simulation": {"realtime": True, "speed": 1.0}}

def get_target_id(target: str) -> str:
    target = target.lower() if isinstance(target, str) else ""
    if target not in TARGETS:
        raise ValueError(f"不支持的目标 {target!r}；当前仅支持：{', '.join(TARGETS)}")
    return target

def validate_project(project: dict[str, Any]) -> dict[str, Any]:
    """Validate project metadata and return a normalized defensive copy."""
    if not isinstance(project, dict):
        raise ValueError("项目必须是 JSON 对象")
    version = project.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError(f"不支持的项目格式版本：{version}")
    target = get_target_id(project.get("target", DEFAULT_TARGET))
    files = project.get("files", {})
    if not isinstance(files, dict) or any(not isinstance(name, str) or not name or not isinstance(content, str) for name, content in files.items()):
        raise ValueError("files 必须是文件名到文本内容的对象")
    circuit = project.get("circuit", {})
    if not isinstance(circuit, dict):
        raise ValueError("circuit 必须是对象")
    components, wires = circuit.get("components", []), circuit.get("wires", [])
    if not isinstance(components, list) or not isinstance(wires, list):
        raise ValueError("circuit.components 和 circuit.wires 必须是数组")
    seen_ids, normalized_components = set(), []
    for i, item in enumerate(components):
        if not isinstance(item, dict):
            raise ValueError(f"元件 #{i + 1} 必须是对象")
        cid, kind = item.get("id"), item.get("type")
        if not isinstance(cid, str) or not cid.strip() or cid in seen_ids:
            raise ValueError(f"元件 #{i + 1} 的 id 无效或重复")
        if kind not in COMPONENTS:
            raise ValueError(f"元件 {cid} 的类型不支持：{kind}")
        seen_ids.add(cid)
        props = item.get("props", {})
        if not isinstance(props, dict):
            raise ValueError(f"元件 {cid} 的 props 必须是对象")
        normalized = deepcopy(item)
        normalized["props"] = deepcopy(props)
        for axis in ("x", "y"):
            value = item.get(axis, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"元件 {cid} 的 {axis} 坐标必须是数字")
        normalized_components.append(normalized)
    by_id = {item["id"]: item for item in normalized_components}
    normalized_wires = []
    for i, wire in enumerate(wires):
        if not isinstance(wire, dict):
            raise ValueError(f"连线 #{i + 1} 必须是对象")
        normalized = deepcopy(wire)
        for endpoint_name in ("a", "b"):
            endpoint = wire.get(endpoint_name)
            if not isinstance(endpoint, (list, tuple)) or len(endpoint) != 2:
                raise ValueError(f"连线 #{i + 1} 的 {endpoint_name} 端点格式无效")
            cid, pin = endpoint
            component = by_id.get(cid)
            if component is None:
                raise ValueError(f"连线 #{i + 1} 引用了不存在的元件：{cid}")
            if pin not in COMPONENTS[component["type"]]["pins"]:
                raise ValueError(f"元件 {cid} 不存在引脚 {pin}")
            normalized[endpoint_name] = [cid, pin]
        normalized_wires.append(normalized)
    simulation = project.get("simulation", {})
    if not isinstance(simulation, dict):
        raise ValueError("simulation 必须是对象")
    return {"schema_version": SCHEMA_VERSION, "name": str(project.get("name", "Untitled")),
            "target": target, "files": deepcopy(files),
            "circuit": {"components": normalized_components, "wires": normalized_wires},
            "simulation": deepcopy(simulation)}

def from_legacy_circuit(circuit: dict[str, Any], *, name: str = "Imported circuit",
                        target: str = DEFAULT_TARGET) -> dict[str, Any]:
    if not isinstance(circuit, dict):
        raise ValueError("原理图必须是对象")
    return validate_project(new_project(name=name, target=target,
        components=circuit.get("components", []), wires=circuit.get("wires", [])))

def to_legacy_circuit(project: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(validate_project(project)["circuit"])

def dump_project(project: dict[str, Any], path: str | Path | None = None) -> str:
    payload = json.dumps(validate_project(project), ensure_ascii=False, indent=2) + "\n"
    if path is not None:
        Path(path).write_text(payload, encoding="utf-8")
    return payload

def load_project(path: str | Path) -> dict[str, Any]:
    return validate_project(json.loads(Path(path).read_text(encoding="utf-8")))
