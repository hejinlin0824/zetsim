"""Deterministic local build cache for zetsim firmware projects."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_CACHE_ROOT = _REPO / ".zetsim" / "cache" / "build"

def _digest_file(digest, path: Path, root: Path) -> None:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = str(path.resolve())
    digest.update(relative.encode("utf-8", "surrogatepass"))
    digest.update(b"\0")
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    digest.update(b"\0")

def build_cache_key(project_dir: str | Path, gcc: str, *, hal_project: bool, flags: list[str]) -> str:
    """Hash toolchain identity, flags, project sources, and relevant CMSIS/HAL inputs."""
    project = Path(project_dir).resolve()
    digest = hashlib.sha256()
    digest.update(b"zetsim-build-cache-v1\0")
    digest.update(os.path.normcase(os.path.realpath(gcc)).encode("utf-8", "surrogatepass"))
    digest.update(json.dumps({"hal_project": hal_project, "flags": flags}, sort_keys=True).encode())
    try:
        version = subprocess.run([gcc, "--version"], capture_output=True, text=True, errors="replace", timeout=15)
        digest.update((version.stdout + version.stderr + str(version.returncode)).encode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError) as exc:
        digest.update(repr(exc).encode("utf-8", "replace"))
    inputs = []
    for pattern in ("*.c", "*.h", "*.S", "*.s", "*.ld", "*.txt"):
        inputs.extend(project.glob(pattern))
    roots = [
        _REPO / "third_party" / "cmsis-device-f1" / "Include",
        _REPO / "third_party" / "cmsis-device-f1" / "Source",
        _REPO / "third_party" / "CMSIS_5" / "CMSIS" / "Core" / "Include",
    ]
    if hal_project:
        roots.extend([
            _REPO / "third_party" / "stm32f1xx-hal-driver" / "Inc",
            _REPO / "third_party" / "stm32f1xx-hal-driver" / "Src",
        ])
    for root in roots:
        if root.is_dir():
            inputs.extend(p for p in root.rglob("*") if p.is_file())
    seen = set()
    for path in sorted(inputs, key=lambda p: str(p).casefold()):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        root = project if resolved == project or project in resolved.parents else _REPO
        _digest_file(digest, path, root)
    return digest.hexdigest()

def restore_cached_build(project_dir: str | Path, key: str) -> bool:
    project = Path(project_dir)
    entry = _CACHE_ROOT / key
    if not (entry / "firmware.hex").is_file() or not (entry / "firmware.elf").is_file():
        return False
    shutil.copy2(entry / "firmware.hex", project / "firmware.hex")
    shutil.copy2(entry / "firmware.elf", project / "firmware.elf")
    return True

def store_cached_build(project_dir: str | Path, key: str) -> None:
    project = Path(project_dir)
    entry = _CACHE_ROOT / key
    if not (project / "firmware.hex").is_file() or not (project / "firmware.elf").is_file():
        return
    entry.mkdir(parents=True, exist_ok=True)
    for source in (project / "firmware.hex", project / "firmware.elf"):
        temp = entry / (source.name + ".tmp")
        shutil.copy2(source, temp)
        temp.replace(entry / source.name)
