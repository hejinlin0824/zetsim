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
