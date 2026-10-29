"""Validated board metadata registry for physical development-board definitions.

This describes board connectors and onboard parts; it is deliberately separate
from the SoC target registry and does not claim a peripheral is emulated merely
because that peripheral appears in the chip datasheet.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any

from .targets import TARGETS

_DATA_DIR = Path(__file__).resolve().parent / "data" / "boards"
_GPIO_RE = re.compile(r"^GPIO(\d+)$")
_POWER_RE = re.compile(r"^power\((\d+(?:\.\d+)?)\)$")


@dataclass(frozen=True)
class BoardPin:
    name: str
    target: str
    kind: str
    gpio: int | None = None
    voltage: float | None = None
    constraints: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "kind": self.kind,
            "gpio": self.gpio,
            "voltage": self.voltage,
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True)
class BoardDefinition:
    id: str
    name: str
    mcu: str
    target: str
    fqbn: str | None
    pins: dict[str, BoardPin]
    headers: dict[str, tuple[str, ...]]
    leds: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "mcu": self.mcu,
            "target": self.target,
            "fqbn": self.fqbn,
            "pins": {name: pin.as_dict() for name, pin in self.pins.items()},
            "headers": {name: list(pins) for name, pins in self.headers.items()},
            "leds": [dict(led) for led in self.leds],
            "metadata": dict(self.metadata),
        }


def _strip_json_comments(source: str) -> str:
    """Remove // and /* */ comments without corrupting quoted URL/string data."""
    result: list[str] = []
    i = 0
    in_string = False
    escaped = False
    while i < len(source):
        char = source[i]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue
        if char == "/" and i + 1 < len(source) and source[i + 1] == "/":
            i += 2
            while i < len(source) and source[i] not in "\r\n":
                i += 1
            continue
        if char == "/" and i + 1 < len(source) and source[i + 1] == "*":
            i += 2
            while i + 1 < len(source) and source[i:i + 2] != "*/":
                if source[i] in "\r\n":
                    result.append(source[i])
                i += 1
            if i + 1 >= len(source):
                raise ValueError("JSONC 中存在未闭合的块注释")
            i += 2
            continue
        result.append(char)
        i += 1
    if in_string:
        raise ValueError("JSONC 中存在未闭合的字符串")
    return "".join(result)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _pin_kind(target: str) -> tuple[str, int | None, float | None]:
    gpio_match = _GPIO_RE.fullmatch(target)
    if gpio_match:
        return "gpio", int(gpio_match.group(1)), None
    power_match = _POWER_RE.fullmatch(target)
    if power_match:
        return "power", None, float(power_match.group(1))
    if target == "GND":
        return "ground", None, 0.0
    if target == "CHIP_PU":
        return "reset", None, None
    return "signal", None, None


def validate_board(data: dict[str, Any], *, fallback_id: str = "board") -> BoardDefinition:
    """Validate and normalize one board-definition object."""
    if not isinstance(data, dict):
        raise ValueError("板卡定义必须是 JSON 对象")
    board_id = data.get("id", fallback_id)
    if not isinstance(board_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", board_id):
        raise ValueError("板卡 id 只能包含小写字母、数字、下划线和连字符")
    name = data.get("name")
    mcu = data.get("mcu")
    target = data.get("target")
    if not all(isinstance(value, str) and value.strip() for value in (name, mcu, target)):
        raise ValueError("板卡 name、mcu 和 target 均为必填字符串")
    if target not in TARGETS:
        raise ValueError(f"板卡 {board_id} 引用了不支持的目标：{target}")
    fqbn = data.get("fqbn")
    if fqbn is not None and (not isinstance(fqbn, str) or not fqbn.strip()):
        raise ValueError("fqbn 必须是非空字符串或 null")

    raw_pins = data.get("pins")
    if not isinstance(raw_pins, dict) or not raw_pins:
        raise ValueError("板卡 pins 必须是非空对象")
    raw_constraints = data.get("gpio_constraints", {})
    if not isinstance(raw_constraints, dict):
        raise ValueError("gpio_constraints 必须是对象")
    constraints: dict[str, tuple[str, ...]] = {}
    for gpio_name, values in raw_constraints.items():
        if not isinstance(gpio_name, str) or not _GPIO_RE.fullmatch(gpio_name):
            raise ValueError(f"无效的 GPIO 约束名称：{gpio_name}")
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError(f"{gpio_name} 的约束必须是字符串数组")
        constraints[gpio_name] = tuple(values)

    pins: dict[str, BoardPin] = {}
    for pin_name, pin_data in raw_pins.items():
        if not isinstance(pin_name, str) or not pin_name.strip():
            raise ValueError("板卡引脚名称必须是非空字符串")
        if not isinstance(pin_data, dict):
            raise ValueError(f"引脚 {pin_name} 必须是对象")
        mapped_target = pin_data.get("target")
        if not isinstance(mapped_target, str) or not mapped_target.strip():
            raise ValueError(f"引脚 {pin_name} 缺少 target")
        kind, gpio, voltage = _pin_kind(mapped_target)
        if "x" in pin_data and not _finite_number(pin_data["x"]):
            raise ValueError(f"引脚 {pin_name} 的 x 必须是有限数字")
        if "y" in pin_data and not _finite_number(pin_data["y"]):
            raise ValueError(f"引脚 {pin_name} 的 y 必须是有限数字")
        if gpio is not None and gpio in range(49):
            gpio_constraints = constraints.get(f"GPIO{gpio}", ())
        else:
            gpio_constraints = ()
        pins[pin_name] = BoardPin(
            name=pin_name,
            target=mapped_target,
            kind=kind,
            gpio=gpio,
            voltage=voltage,
            constraints=gpio_constraints,
        )

    raw_headers = data.get("headers", {})
    if not isinstance(raw_headers, dict):
        raise ValueError("headers 必须是对象")
    headers: dict[str, tuple[str, ...]] = {}
    for header_name, members in raw_headers.items():
        if not isinstance(header_name, str) or not isinstance(members, list):
            raise ValueError(f"板卡 header {header_name} 格式无效")
        if any(not isinstance(pin_name, str) or pin_name not in pins for pin_name in members):
            raise ValueError(f"板卡 header {header_name} 引用了不存在的引脚")
        if len(members) != len(set(members)):
            raise ValueError(f"板卡 header {header_name} 存在重复引脚")
        headers[header_name] = tuple(members)

    raw_leds = data.get("leds", [])
    if not isinstance(raw_leds, list):
        raise ValueError("leds 必须是数组")
    leds: list[dict[str, Any]] = []
    seen_led_ids: set[str] = set()
    for led in raw_leds:
        if not isinstance(led, dict):
            raise ValueError("每个板载 LED 必须是对象")
        led_id, led_type = led.get("id"), led.get("type")
        led_pins = led.get("pins", {})
        if not isinstance(led_id, str) or not led_id or led_id in seen_led_ids:
            raise ValueError(f"板载 LED id 无效或重复：{led_id}")
        if not isinstance(led_type, str) or not led_type:
            raise ValueError(f"板载 LED {led_id} 缺少 type")
        if not isinstance(led_pins, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in led_pins.items()
        ):
            raise ValueError(f"板载 LED {led_id} 的 pins 必须是字符串映射")
        seen_led_ids.add(led_id)
        leds.append(dict(led))

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("metadata 必须是对象")
    return BoardDefinition(
        id=board_id,
        name=name,
        mcu=mcu,
        target=target,
        fqbn=fqbn,
        pins=pins,
        headers=headers,
        leds=tuple(leds),
        metadata=dict(metadata),
    )


def load_board(path: str | Path) -> BoardDefinition:
    """Load and validate a board JSON/JSONC file from disk."""
    board_path = Path(path)
    try:
        source = board_path.read_text(encoding="utf-8")
        payload = json.loads(_strip_json_comments(source))
    except json.JSONDecodeError as exc:
        raise ValueError(f"板卡定义不是有效 JSON/JSONC：{board_path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"无法读取板卡定义 {board_path}: {exc}") from exc
    return validate_board(payload, fallback_id=board_path.stem)


def board_catalog() -> list[dict[str, Any]]:
    """Return API-safe board metadata, loaded from local version-controlled JSON."""
    if not _DATA_DIR.is_dir():
        return []
    return [load_board(path).as_dict() for path in sorted(_DATA_DIR.glob("*.json"))]


def get_board(board_id: str) -> BoardDefinition:
    for item in board_catalog():
        if item["id"] == board_id:
            return load_board(_DATA_DIR / f"{board_id}.json")
    raise ValueError(f"不存在板卡：{board_id}")
