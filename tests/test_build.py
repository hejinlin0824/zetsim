"""Build helper regression tests; no real ARM toolchain is required."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from zetsim import build


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "sample"
    project.mkdir()
    (project / "main.c").write_text("int main(void) { return 0; }", encoding="utf-8")
    (project / "link.ld").write_text("/* fake linker script for mocked build */", encoding="utf-8")
    return project


def test_build_uses_gcc_selected_libgcc_archive_and_native_post_link_paths(
    tmp_path: Path, monkeypatch
) -> None:
    project = _make_project(tmp_path)
    tool_dir = tmp_path / "toolchain with spaces" / "bin"
    gcc_name = "arm-none-eabi-gcc.exe" if os.name == "nt" else "arm-none-eabi-gcc"
    gcc = tool_dir / gcc_name
    suffix = ".exe" if os.name == "nt" else ""
    expected_objcopy = str(tool_dir / ("arm-none-eabi-objcopy" + suffix))
    expected_size = str(tool_dir / ("arm-none-eabi-size" + suffix))
    libgcc = tmp_path / "toolchain with spaces" / "lib" / "gcc" / "arm-none-eabi" / "15.2.1" / "thumb" / "v7-m" / "nofp" / "libgcc.a"
    libgcc.parent.mkdir(parents=True)
    libgcc.write_bytes(b"fake archive for mocked subprocess")

    monkeypatch.setattr(build, "find_gcc", lambda: str(gcc))
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        command = [str(part) for part in args]
        calls.append(command)
        if "-print-libgcc-file-name" in command:
            stdout = str(libgcc) + "\n"
        elif "arm-none-eabi-size" in command[0]:
            stdout = "text data bss dec hex filename\n100 0 0 100 64 firmware.elf\n"
        else:
            stdout = ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    ok, log = build.build_project(project)

    assert ok, log
    assert "-print-libgcc-file-name" in calls[0]
    link_call = next(call for call in calls if "-T" in call)
    objcopy_call = next(call for call in calls if call[0] == expected_objcopy)
    size_call = next(call for call in calls if call[0] == expected_size)
    assert str(libgcc.resolve()) in link_call, "link must use GCC selected runtime archive"
    assert "-L" in link_call
    search_index = link_call.index("-L")
    assert link_call[search_index + 1] == str(libgcc.parent)
    assert "-lgcc" not in link_call
    assert objcopy_call[0] == expected_objcopy
    assert size_call[0] == expected_size


def test_build_reports_missing_libgcc_before_invoking_linker(
    tmp_path: Path, monkeypatch
) -> None:
    project = _make_project(tmp_path)
    gcc = tmp_path / "broken-toolchain" / "bin" / "arm-none-eabi-gcc.exe"
    missing = tmp_path / "broken-toolchain" / "lib" / "libgcc.a"
    monkeypatch.setattr(build, "find_gcc", lambda: str(gcc))
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        command = [str(part) for part in args]
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=str(missing) + "\n", stderr="")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    ok, log = build.build_project(project)

    assert not ok
    assert "工具链运行库缺失" in log
    assert str(missing) in log
    assert len(calls) == 1, "do not invoke the linker without a verified runtime archive"
