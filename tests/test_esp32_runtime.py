from __future__ import annotations

from pathlib import Path

from zetsim.esp32_runtime import ESP32RuntimeObserver

ROOT = Path(__file__).resolve().parents[1]


def test_esp32_runtime_observer_tracks_boot_layers_and_gpio_edges():
    observer = ESP32RuntimeObserver(max_lines=30, max_samples=20)
    observer.set_process_state(True)
    observer.ingest(
        "ESP-ROM:esp32s3-20210327\r\n"
        "rst:0x1 (POWERON),boot:0x4 (SPI_FLASH_BOOT)\r\n"
        "I (10) boot: stage1\r\n"
        "ZETSIM_ESP32S3_APP_MAIN_ENTERED\r\n"
        "ZETSIM_ESP32S3_GPIO_CONFIG_OK\r\n"
        "I (40) zetsim: ZETSIM_ESP32S3_BOOT_OK\r\n"
        "ZETSIM_ESP32S3_GPIO2=1\r\n"
        "ZETSIM_ESP32S3_GPIO2=0\r\n"
        "temperature:24.5\r\n"
    )
    snapshot = observer.snapshot()
    assert snapshot["status"] == "ready"
    assert snapshot["rom_seen"] is True
    assert snapshot["boot_count"] == 1
    assert snapshot["reset_reason"] == {"code": "0x1", "reason": "POWERON"}
    assert snapshot["app_main_entered"] is True
    assert snapshot["gpio_configured"] is True
    assert snapshot["app_ready"] is True
    assert snapshot["gpio_levels"] == {"2": 0}
    assert snapshot["plot_series"]["GPIO2"][-1]["value"] == 0.0
    assert snapshot["plot_series"]["temperature"][-1]["value"] == 24.5
    assert snapshot["simulation_time_ms"] == 40


def test_esp32_runtime_observer_preserves_panic_evidence_and_bounds_logs():
    observer = ESP32RuntimeObserver(max_lines=20, max_samples=10)
    observer.set_process_state(True)
    observer.ingest("Guru Meditation Error: Core 0 panic'ed (LoadProhibited).\n")
    snapshot = observer.snapshot()
    assert snapshot["status"] == "panic"
    assert snapshot["panic_count"] == 1
    observer.set_process_state(False, exit_code=1)
    snapshot = observer.snapshot()
    assert snapshot["status"] == "failed"
    assert snapshot["exit_code"] == 1


def test_esp32_runtime_observer_keeps_partial_uart_lines_between_chunks():
    observer = ESP32RuntimeObserver()
    observer.set_process_state(True)
    observer.ingest("ZETSIM_ESP32S3_APP_MAIN_")
    assert observer.snapshot()["app_main_entered"] is False
    observer.ingest("ENTERED\n")
    assert observer.snapshot()["app_main_entered"] is True


def test_esp32_runtime_observer_reboot_resets_current_boot_markers_but_keeps_history():
    observer = ESP32RuntimeObserver()
    observer.set_process_state(True)
    observer.ingest(
        "ESP-ROM:esp32s3-20210327\n"
        "ZETSIM_ESP32S3_APP_MAIN_ENTERED\n"
        "ESP-ROM:esp32s3-20210327\n"
    )
    snapshot = observer.snapshot()
    assert snapshot["boot_count"] == 2
    assert snapshot["app_main_entered"] is False
    assert len(snapshot["uart_lines"]) == 3



def test_runtime_monitor_ui_is_wired_to_esp32_runtime_api():
    html = (ROOT / "zetsim" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="esp32RuntimeModal"' in html
    assert 'id="esp32Btn"' in html
    assert 'id="esp32Plot"' in html
    assert 'id="esp32SerialInput"' in html
    assert '/api/esp32/runtime/start' in html
    assert '/api/esp32/runtime/serial' in html
    assert 'ZETSIM_ESP32S3_GPIO' in html or 'gpio_levels' in html



def test_esp32_process_tree_parser_orders_descendants_before_termination():
    from zetsim.esp32_runtime import ESP32RuntimeSession

    process_table = "10 1\n20 10\n21 10\n30 20\n40 2\n"
    assert ESP32RuntimeSession._descendant_pids_from_ps(10, process_table) == [20, 21, 30]


def test_runtime_monitor_board_map_uses_board_registry_metadata():
    html = (ROOT / "zetsim" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="esp32BoardHeaders"' in html
    assert 'id="esp32BoardDimensions"' in html
    assert 'request("/api/boards")' in html
    assert "esp32-s3-devkitc-1" in html
    assert "board.pins" in html
    assert "board.leds" in html


def test_runtime_observer_tracks_gpio_readback_and_mismatch_events_separately():
    observer=ESP32RuntimeObserver(max_lines=30,max_samples=20)
    observer.set_process_state(True)
    observer.ingest(
        "ZETSIM_ESP32S3_GPIO2=1\n"
        "ZETSIM_ESP32S3_GPIO2_READBACK=0\n"
        "ZETSIM_ESP32S3_GPIO2_READBACK_MISMATCH expected=1 got=0\n"
        "ZETSIM_ESP32S3_GPIO2=0\n"
        "ZETSIM_ESP32S3_GPIO2_READBACK=0\n"
    )
    snapshot=observer.snapshot()
    assert snapshot["gpio_levels"]=={"2":0}
    assert snapshot["gpio_readback_levels"]=={"2":0}
    assert snapshot["gpio_output_mismatch_count"]==1
    assert snapshot["gpio_output_mismatches"][0]["expected"]==1
    assert snapshot["gpio_output_mismatches"][0]["got"]==0
    assert snapshot["plot_series"]["GPIO2"][-1]["value"]==0.0
    assert snapshot["plot_series"]["GPIO2_READBACK"][-1]["value"]==0.0


def test_esp_emu_discovery_finds_repo_local_pinned_binary(tmp_path: Path):
    from zetsim.esp32_runtime import ESP32RuntimeSession

    executable = tmp_path / ".tools" / "esp-emu-0.51.0" / "esp-emu"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test binary placeholder")
    found = ESP32RuntimeSession._find_esp_emu({"PATH": ""}, repo_root=tmp_path)
    assert found == executable.resolve()


def test_esp_emu_discovery_honors_explicit_environment_override(tmp_path: Path):
    from zetsim.esp32_runtime import ESP32RuntimeSession

    executable = tmp_path / "custom-esp-emu"
    executable.write_bytes(b"test binary placeholder")
    found = ESP32RuntimeSession._find_esp_emu(
        {"PATH": "", "ZETSIM_ESP_EMU": str(executable)}, repo_root=tmp_path
    )
    assert found == executable.resolve()


def test_idf_project_name_is_read_from_cmake_not_directory_name(tmp_path: Path):
    from zetsim.esp32_runtime import ESP32RuntimeSession

    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\nproject(zetsim_esp32s3_blink)\n",
        encoding="utf-8",
    )
    assert ESP32RuntimeSession._project_name(tmp_path) == "zetsim_esp32s3_blink"


def test_runtime_snapshot_discloses_selected_backend():
    from zetsim.esp32_runtime import ESP32RuntimeSession

    session = ESP32RuntimeSession()
    assert session.snapshot()["backend"] == "none"
    session._engine_kind = "esp-emu"
    assert session.snapshot()["backend"] == "esp-emu"



def test_esp_emu_install_hint_is_platform_aware_for_windows():
    from zetsim.esp32_runtime import ESP32RuntimeSession

    hint = ESP32RuntimeSession._esp_emu_install_hint("nt")
    assert "没有列出 Windows 原生二进制" in hint
    assert "WSL2 Ubuntu" in hint
    assert "Espressif QEMU" in hint
    assert "0.51.0" in hint


def test_esp_emu_install_hint_has_pinned_posix_install_command():
    from zetsim.esp32_runtime import ESP32RuntimeSession

    hint = ESP32RuntimeSession._esp_emu_install_hint("posix")
    assert "--version 0.51.0" in hint
    assert ".tools/esp-emu-0.51.0" in hint
