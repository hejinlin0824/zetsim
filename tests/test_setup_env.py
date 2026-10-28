"""Environment detector tests for the ARM toolchain's real link capability."""
from __future__ import annotations

import subprocess
from pathlib import Path

import setup_env


def test_non_ascii_windows_checkout_uses_user_local_ascii_toolchain(monkeypatch, tmp_path: Path):
    checkout = Path(tmp_path) / "含中文目录" / "zetsim"
    local_app_data = tmp_path / "LocalAppData"
    monkeypatch.setattr(setup_env, "ROOT", checkout)
    monkeypatch.setattr(setup_env.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("ZETSIM_TOOLCHAIN_DIR", raising=False)

    result = setup_env.preferred_toolchain_dir()

    assert result == local_app_data / "zetsim" / "toolchain"
    assert str(result).isascii()


def test_link_smoke_test_invokes_real_linker_with_selected_libgcc(monkeypatch, tmp_path: Path):
    gcc = tmp_path / "arm-toolchain" / "bin" / "arm-none-eabi-gcc.exe"
    libgcc = tmp_path / "arm-toolchain" / "lib" / "thumb" / "v7-m" / "libgcc.a"
    libgcc.parent.mkdir(parents=True)
    libgcc.write_bytes(b"mock archive")
    monkeypatch.setattr(setup_env, "_libgcc_path", lambda _gcc: libgcc)
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = [str(arg) for arg in args]
        captured["cwd"] = kwargs["cwd"]
        out = Path(captured["args"][captured["args"].index("-o") + 1])
        out.write_bytes(b"mock elf")
        return subprocess.CompletedProcess(captured["args"], 0, stdout="", stderr="")

    monkeypatch.setattr(setup_env.subprocess, "run", fake_run)
    ok, detail = setup_env._link_smoke_test(gcc)

    assert ok, detail
    assert "-mcpu=cortex-m3" in captured["args"]
    assert "-mthumb" in captured["args"]
    assert "-nostdlib" in captured["args"]
    assert "-L" in captured["args"]
    assert str(libgcc.parent) in captured["args"]
    assert str(libgcc) in captured["args"]
    assert any(arg.startswith("-Wl,-T,") for arg in captured["args"])
    assert Path(captured["cwd"]).name.startswith("zetsim-arm-link-check-")


def test_link_smoke_test_explains_missing_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(setup_env, "_libgcc_path", lambda _gcc: None)

    ok, detail = setup_env._link_smoke_test(tmp_path / "missing-gcc.exe")

    assert not ok
    assert "libgcc.a" in detail
