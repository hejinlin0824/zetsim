from __future__ import annotations

import subprocess
from pathlib import Path

from zetsim import esp32


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "esp32s3_blink"


def _fake_idf_environment(tmp_path: Path) -> dict[str, str]:
    idf_root = tmp_path / "esp-idf"
    (idf_root / "tools").mkdir(parents=True)
    (idf_root / "tools" / "idf.py").write_text("# fake idf.py\n", encoding="utf-8")
    python_env = tmp_path / "idf-python"
    python_bin = python_env / "Scripts" / "python.exe"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_bytes(b"")
    return {
        "IDF_PATH": str(idf_root),
        "IDF_PYTHON_ENV_PATH": str(python_env),
        "PATH": "",
    }


def _fake_project(tmp_path: Path) -> Path:
    project = tmp_path / "esp32_project"
    (project / "main").mkdir(parents=True)
    (project / "CMakeLists.txt").write_text("project(fake)\n", encoding="utf-8")
    (project / "main" / "CMakeLists.txt").write_text(
        'idf_component_register(SRCS "main.c")\n', encoding="utf-8"
    )
    (project / "main" / "main.c").write_text("void app_main(void) {}\n", encoding="utf-8")
    return project


def test_real_project_uses_native_esp_idf_layout() -> None:
    assert (PROJECT / "CMakeLists.txt").is_file()
    assert (PROJECT / "main" / "CMakeLists.txt").is_file()
    assert (PROJECT / "main" / "main.c").is_file()
    assert not (PROJECT / "main.c").exists()
    assert not (PROJECT / "link.ld").exists()


def test_qemu_project_selects_uart_console_for_monitor() -> None:
    sdkconfig = (PROJECT / "sdkconfig.defaults").read_text(encoding="utf-8")
    assert 'CONFIG_ESP_CONSOLE_UART_DEFAULT=y' in sdkconfig
    # This dedicated QEMU fixture avoids the pre-app_main TWDT interrupt-allocation
    # panic; the setting must not be treated as a global zetsim default.
    assert "CONFIG_ESP_TASK_WDT_INIT=n" in sdkconfig


def test_resolve_idf_command_prefers_idf_managed_python(tmp_path: Path) -> None:
    env = _fake_idf_environment(tmp_path)
    command, error = esp32.resolve_idf_command(env)
    assert error is None
    assert command == [
        str(Path(env["IDF_PYTHON_ENV_PATH"]) / "Scripts" / "python.exe"),
        str(Path(env["IDF_PATH"]) / "tools" / "idf.py"),
    ]


def test_build_invokes_idf_py_with_esp32s3_target(tmp_path: Path) -> None:
    env = _fake_idf_environment(tmp_path)
    project = _fake_project(tmp_path)
    calls: list[dict] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="ESP-IDF build success", stderr="")

    ok, log = esp32.build_esp32_project(project, env=env, runner=fake_run)
    assert ok, log
    assert len(calls) == 1
    call = calls[0]
    assert call["command"][-3:] == ["-C", str(project), "build"]
    assert call["env"]["IDF_TARGET"] == "esp32s3"
    assert call["cwd"] == str(project)
    assert "ESP-IDF build success" in log


def test_qemu_runner_uses_official_qemu_monitor_command(tmp_path: Path) -> None:
    env = _fake_idf_environment(tmp_path)
    project = _fake_project(tmp_path)
    calls: list[dict] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0)

    rc = esp32.run_esp32_project(project, graphics=True, env=env, runner=fake_run)
    assert rc == 0
    assert calls[0]["command"][-5:] == ["-C", str(project), "qemu", "--graphics", "monitor"]
    assert calls[0]["env"]["IDF_TARGET"] == "esp32s3"


def test_missing_idf_environment_is_actionable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("IDF_PATH", raising=False)
    monkeypatch.setattr(esp32.shutil, "which", lambda *args, **kwargs: None)
    command, error = esp32.resolve_idf_command({"PATH": ""})
    assert command is None
    assert error and "ESP-IDF" in error



def test_smoke_script_has_layered_boot_markers_and_panic_symbolization():
    script = (ROOT / ".github" / "scripts" / "esp32s3-qemu-smoke.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "Upload ESP32-S3 smoke evidence" in workflow
    assert "if: always()" in workflow
    assert "actions/upload-artifact@v4" in workflow
    for token in (
        "Guru Meditation Error",
        "xtensa-esp32s3-elf-addr2line",
        "xtensa-esp-elf-addr2line",
        "awk '/PC[[:space:]]*:/",
        "make_artifacts_readable",
        "chmod 0644",
        "ESP-ROM:esp32s3",
        "ZETSIM_ESP32S3_APP_MAIN_ENTERED",
        "ZETSIM_ESP32S3_GPIO_CONFIG_OK",
        "ZETSIM_ESP32S3_BOOT_OK",
        "ZETSIM_ESP32S3_GPIO2=",
        "ZETSIM_ESP32S3_GPIO2_READBACK=1",
        "ZETSIM_ESP32S3_GPIO2_READBACK=0",
        "ZETSIM_ESP32S3_GPIO2_READBACK_MISMATCH",
    ):
        assert token in script


def test_esp32s3_blink_firmware_checks_gpio_output_readback():
    source = (ROOT / "projects" / "esp32s3_blink" / "main" / "main.c").read_text(encoding="utf-8")
    assert "gpio_set_level(BLINK_GPIO, level)" in source
    assert "gpio_get_level(BLINK_GPIO)" in source
    assert "ZETSIM_ESP32S3_GPIO2_READBACK=%d" in source
    assert "ZETSIM_ESP32S3_GPIO2_READBACK_MISMATCH" in source
