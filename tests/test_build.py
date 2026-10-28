"""Build helper regression tests; no real ARM toolchain is required."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from zetsim import build


def test_build_resolves_post_link_tools_using_native_paths(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "sample"
    project.mkdir()
    (project / "main.c").write_text("int main(void) { return 0; }", encoding="utf-8")
    (project / "link.ld").write_text("/* fake linker script for mocked build */", encoding="utf-8")
    tool_dir = tmp_path / "toolchain" / "bin"
    gcc_name = "arm-none-eabi-gcc.exe" if os.name == "nt" else "arm-none-eabi-gcc"
    gcc = tool_dir / gcc_name
    suffix = ".exe" if os.name == "nt" else ""
    expected_objcopy = str(tool_dir / ("arm-none-eabi-objcopy" + suffix))
    expected_size = str(tool_dir / ("arm-none-eabi-size" + suffix))

    monkeypatch.setattr(build, "find_gcc", lambda: str(gcc))
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        command = [str(part) for part in args]
        calls.append(command)
        if "arm-none-eabi-size" in command[0]:
            stdout = "text data bss dec hex filename\n100 0 0 100 64 firmware.elf\n"
        else:
            stdout = ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    ok, log = build.build_project(project)

    assert ok, log
    assert calls[1][0] == expected_objcopy
    assert calls[2][0] == expected_size
