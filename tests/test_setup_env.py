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



def test_download_toolchain_creates_nested_destination_and_reuses_cached_zip(
    monkeypatch, tmp_path: Path
):
    import io
    import json
    import zipfile

    root = tmp_path / "repo"
    root.mkdir()
    asset_name = "xpack-arm-none-eabi-gcc-15.2.1-1.1-win32-x64.zip"
    cached_archive = root / asset_name
    with zipfile.ZipFile(cached_archive, "w") as archive:
        archive.writestr("toolchain/marker.txt", "cached package")

    target = tmp_path / "LocalAppData" / "zetsim" / "toolchain"
    expected_gcc = target / "toolchain" / "bin" / "arm-none-eabi-gcc.exe"
    monkeypatch.setattr(setup_env, "ROOT", root)
    monkeypatch.setattr(setup_env, "TOOLCHAIN_DIR", target)
    monkeypatch.setattr(setup_env, "xpack_platform", lambda: "win32-x64")
    payload = {
        "tag_name": "v15.2.1-1.1",
        "assets": [{
            "name": asset_name,
            "browser_download_url": "https://example.invalid/toolchain.zip",
        }],
    }
    monkeypatch.setattr(
        setup_env.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )
    downloads = []

    def unexpected_download(url, path):
        downloads.append((url, path))
        raise AssertionError("cached archive should be reused")

    monkeypatch.setattr(setup_env.urllib.request, "urlretrieve", unexpected_download)
    monkeypatch.setattr(setup_env, "find_gcc", lambda: expected_gcc)

    found = setup_env.download_toolchain()

    assert found == expected_gcc
    assert target.is_dir()
    assert (target / "toolchain" / "marker.txt").read_text(encoding="utf-8") == "cached package"
    assert not cached_archive.exists()
    assert downloads == []
