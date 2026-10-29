# ESP32-S3 hardware digitalization and simulation plan

## Source hierarchy

Use the chip-specific **ESP32-S3 Series Datasheet** and **ESP32-S3 Technical Reference Manual (TRM)**, not the classic ESP32 TRM as a substitute. The official Espressif document index lists ESP32-S3 Datasheet v2.2 (2026-03-05) and ESP32-S3 TRM v1.8 (2026-03-04). The Chinese datasheet identifies the S3 as a dual-core Xtensa LX7 SoC with 45 programmable GPIOs and documents UART, I2C, SPI, LED PWM, RMT, ADC, timers, watchdogs, and related capabilities.

- Datasheet (Chinese PDF): https://documentation.espressif.com/esp32-s3_datasheet_cn.pdf
- ESP32-S3 Technical Reference Manual (Chinese): https://documentation.espressif.com/esp32-s3_technical_reference_manual_cn.pdf
- Official documents index and versions: https://www.espressif.com/en/support/download/documents/chips
- ESP32-S3-DevKitC-1 hardware guide: https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/user_guide.html
- QEMU for ESP32-S3 usage notes: https://github.com/espressif/esp-toolchain-docs/blob/main/qemu/esp32s3/README.md
- Curated board pin mapping reference: https://github.com/wokwi/wokwi-boards/blob/main/boards/esp32-s3-devkitc-1/board.json

## One technical manual, four separate models

Do not flatten the whole manual into one giant table and treat it as an emulator. Maintain separate layers with links between them:

1. **SoC specification** — chip family, GPIO capabilities and restrictions, peripheral inventory, pin mux, reset/boot straps, clock and interrupt relationships.
2. **Board specification** — actual exposed header aliases (for example TX/RX), power/reset pins, module/flash configuration, onboard indicators, and board revision.
3. **Register specification** — peripheral base address, register offset, access type, reset value, field masks/enumerations, read/write side effects, interrupt bits, clock/reset dependencies.
4. **Runtime implementation and fidelity** — which register behaviours are implemented by Espressif QEMU, which are only metadata, what the app/CI proves, and known differences from hardware.

Each register/peripheral item should carry a fidelity state such as `documented`, `metadata-only`, `implemented`, `QEMU-covered`, and `hardware-verified`. Never mark a model as implemented only because the datasheet names the peripheral.

## Important distinctions learned from the datasheet

- The SoC has a flexible GPIO matrix; UART signals can be routed through GPIO configuration. Board labels TX and RX are board aliases, and for ESP32-S3-DevKitC-1 they are wired to GPIO43 and GPIO44 by default. Do not hard-code these as universal GPIO numbers for every ESP32-S3 board.
- GPIO0, GPIO3, GPIO45, and GPIO46 are strapping-related pins. GPIO0/GPIO46 participate in boot-mode selection; GPIO45 participates in VDD_SPI selection; GPIO3 participates in JTAG-source selection. Board checks should warn when the external circuit drives strap pins to risky levels during reset.
- GPIO19/20 are associated with USB Serial/JTAG, GPIO39–42 with JTAG, GPIO43/44 with UART0, and GPIO33–37 may conflict with Octal SPI flash/PSRAM use. GPIO26–32 require flash/PSRAM reservation checks. These are constraints, not assertions that every module uses those pins identically; module/flash configuration matters.
- The datasheet lists the existence of GPIO, UART, I2C, SPI, LED PWM, RMT, ADC, timers and other blocks. Whether every register and side effect is modelled by the selected QEMU version is a separate testable question.
- A board-level WS2812 RGB LED is not equivalent to a simple binary LED. It requires a timed one-wire symbol decoder (or a QEMU-supported hardware path that provides the actual peripheral behaviour) before its colour can be claimed to be simulated correctly.

## Proposed implementation order

### P0 — establish a trustworthy ESP32-S3 run
- Build with a pinned ESP-IDF version; record QEMU and compiler versions in CI.
- Require a ROM marker, reset/boot marker, an application-entry marker, a post-GPIO-setup marker, and repeated application heartbeat output.
- Treat any Guru Meditation / unhandled panic during the observation interval as failure, even if the app later reboots and prints another marker.
- Decode Xtensa PC/backtrace addresses against the exact ELF generated in that CI run.
- Preserve the complete captured UART log as a CI artifact on both success and failure (follow-up item if artifact upload is added).

### P1 — digitize the board and chip facts without claiming unsupported simulation
- Load versioned local board JSON through `zetsim.boards`, separate from `zetsim.targets` and `zetsim.component_registry`.
- Validate aliases, targets, optional physical coordinates, header membership, board LED declarations, and GPIO constraints.
- Expose a read-only `/api/boards` endpoint so the UI can render board choices from metadata rather than hard-coded labels.
- Add datasheet-derived register metadata in small slices: start with GPIO, IO MUX/GPIO matrix, UART0, clock/reset dependencies, and interrupt routing. Cross-check register addresses and bit fields against the exact ESP-IDF SoC headers and official TRM version.
- Keep metadata-only register descriptions separate from actual register read/write handlers. Only those handlers, with regression tests, count as a model.

### P2 — peripheral models, by measured value
1. GPIO levels/direction and observable pin transitions.
2. UART0 TX/RX transport between guest firmware and the serial monitor.
3. Timer/clock and interrupt semantics needed by the above.
4. WS2812 decoder or RMT/LEDC implementation only after confirming the selected QEMU build's supported device semantics.
5. Extend to I2C/SPI/ADC and more peripherals only with specific example projects and repeatable tests.

## Source/reuse policy

The board JSON in this repository is a curated data model, not a bundled board illustration or renderer. The referenced public board definition is used as a pin-mapping cross-check; no SVG, ROM binary, QEMU source, or Wokwi runtime asset is copied. Keep upstream references and the official chip-document version in the metadata. Re-check module-specific limitations and document versions when the board model is extended.


## First machine-readable register slice: GPIO / IO MUX

The initial catalog is zetsim/data/registers/esp32s3-gpio.json, exposed read-only through GET /api/hardware/registers. It records the GPIO register-summary slice in ESP32-S3 TRM v1.8, section 6.14.1, with offsets relative to DR_REG_GPIO_BASE. The absolute base is intentionally unset until verified against the address-map table in the same source revision.

This catalog is marked fidelity=metadata-only and runtime_implemented=false. It records the documented register names, offsets, access modes, affected GPIO ranges, and W1TS/W1TC write-one side effects. It does not implement memory-mapped register behaviour and does not imply Espressif QEMU covers every register. Before implementing the model, reconcile register fields and reserved bits against the exact TRM v1.8 tables and ESP-IDF v6.1 SoC headers, then add guest-firmware tests for read/write semantics and observable pin edges.


## QEMU smoke fixture: startup Task Watchdog workaround

A symbolized CI backtrace on ESP-IDF v6.1 showed the panic occurs before the application entry point: `main_task` calls `esp_task_wdt_init`, which enters `esp_task_wdt_impl_timer_allocate` and the interrupt allocator before a null-address `LoadProhibited`. This is a QEMU smoke-fixture failure, not evidence that application GPIO code caused the panic.

The dedicated `projects/esp32s3_blink/sdkconfig.defaults` therefore sets `CONFIG_ESP_TASK_WDT_INIT=n` so the test firmware can reach `app_main` and verify UART plus GPIO behavior. This is intentionally scoped to the smoke fixture. It does not change defaults for arbitrary user projects and does not claim that Task Watchdog timer-group interrupts are fully emulated or verified. Re-enable this setting only after the selected QEMU/ESP-IDF pairing passes a dedicated TWDT test.


## Runtime observation and monitor API

The ESP32-S3 runtime adapter in `zetsim/esp32_runtime.py` wraps the interactive `idf.py qemu monitor` session in a pseudo-terminal and parses UART0 output. On Linux/macOS it uses `script`; Windows uses the optional `pywinpty` backend. On Windows install it with `python -m pip install -e ".[windows-pty]"`.

- `GET /api/esp32/runtime` returns boot markers, reset reason, app-entry/GPIO setup state, observed GPIO heartbeat levels, panic count, recent UART lines, plotter samples and measured simulation speed when enough timestamp data exists.
- `POST /api/esp32/runtime/start` with JSON `{"project":"esp32s3_blink"}` starts an ESP-IDF/QEMU monitor session. Only a simple project name under `projects/` is accepted; arbitrary commands and paths are not exposed.
- `POST /api/esp32/runtime/serial` with JSON `{"text":"..."}` sends a line to the emulated UART RX.
- `POST /api/esp32/runtime/stop` terminates the session. The server's shutdown handler also stops its QEMU process.

The observer is bounded: it keeps rolling UART/event windows and bounded numeric plot samples. The fields describe events actually seen on the UART; they are not a substitute for hardware register fidelity. QEMU monitor/PTY availability is checked at runtime, with a clear message when the required platform PTY dependency is missing.


### Second register slice: per-pin IO MUX

A second metadata-only catalogue, `zetsim/data/registers/esp32s3-io-mux.json`, now records all 45 GPIO pad-register aliases present in the ESP-IDF v6.1 ESP32-S3 register header. Each entry carries the GPIO number, the hardware macro alias, the register offset relative to `DR_REG_IO_MUX_BASE`, access metadata, and documented fields for sleep-mode behavior, pull-up/down, input enable, drive strength, MCU function selection, and the short-pulse filter.

The catalog intentionally does not invent the absolute base address, reset values, or per-pin valid `MCU_SEL` enumerations. It remains `metadata-only`; QEMU, not this JSON file, currently provides the guest's MMIO behaviour. The registry loader validates the base-symbol/peripheral pairing, offsets, access modes, and uniqueness of register offsets.


## Versioned SoC specification

The file `zetsim/data/soc/esp32s3.json` records SoC-level facts from the ESP32-S3 datasheet separately from the physical DevKit board definition and the register catalogues. It captures the Xtensa LX7 architecture, GPIO ranges/strapping constraints, common routes, module memory conflicts, and the peripheral inventory described in the referenced datasheet version.

The read-only `GET /api/hardware/soc` endpoint serves this spec to tooling and the workbench. The spec is explicitly marked `runtime_implemented: false`: it is a versioned description of the chip, not an emulator. Board aliases still come from the Board Registry, while register offsets/fields come from the TRM-oriented register catalogues. This separation lets the same SoC spec be reused by multiple compatible board definitions without copying physical-header geometry into chip facts.


## GPIO output/readback regression

The ESP32-S3 blink smoke firmware now reads GPIO2 immediately after each output-level update and emits both the requested level and the readback value. CI requires both levels to be observed and fails if the readback differs from the requested output. This is a firmware-driven test of the selected ESP-IDF/QEMU combination, not proof that every GPIO matrix field or IO MUX register is implemented. If the check fails, retain the captured UART log and treat it as a QEMU fidelity gap to investigate rather than weakening the assertion.


The first readback run consistently returned 0 because the fixture configured GPIO2 as `GPIO_MODE_OUTPUT`, while `gpio_get_level()` samples the input path and ESP-IDF documents that it returns 0 when input is not enabled. The fixture now uses `GPIO_MODE_INPUT_OUTPUT`; this is a correction to the test setup, not evidence of a QEMU bug. If bidirectional mode still fails after this change, then investigate the selected QEMU GPIO feedback model separately.


## GPIO readback: QEMU gap and second emulator

The ESP32-S3 readback fixture uses `GPIO_MODE_INPUT_OUTPUT`, but the current Espressif QEMU run still reports `gpio_get_level(GPIO2) == 0` after both commanded levels. The official QEMU feature matrix explicitly marks GPIO matrix / IOMUX as unsupported, so this result is tracked as a QEMU fidelity gap rather than represented as a firmware GPIO pass: https://github.com/espressif/esp-toolchain-docs/blob/main/qemu/README.md.

CI now keeps the QEMU job as a ROM/boot/app-start/output-call smoke test and writes `GPIO_READBACK_QEMU_FIDELITY_GAP` into the evidence metadata when the mismatch is observed. It additionally runs the same merged ESP-IDF firmware in the separately version-pinned Espressif `esp-emu 0.51.0` emulator, which is published under Apache-2.0 and lists GPIO, UART, timers, and interrupt support. That second run is the acceptance test for commanded GPIO2 high/low and the corresponding input readback; it must show both readback levels and no mismatch marker. `esp-emu` is currently a beta emulator, so its passing test is evidence for the tested firmware and version, not a claim that every ESP32-S3 peripheral is fully modelled.

Sources:
- ESP-IDF GPIO API documents that `gpio_get_level()` reads the input path and returns zero when the pad is not configured as input or input/output: https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/api-reference/peripherals/gpio.html
- Espressif `esp-emu` release 0.51.0 notes and documented installation: https://github.com/espressif/esp-emulator/releases/tag/v0.51.0
- `esp-emu` README and peripheral list: https://github.com/espressif/esp-emulator/blob/v0.51.0/README.md


## UART1 external-device loopback regression

The dedicated ESP-IDF project `projects/esp32s3_uart1_echo` configures UART1 at 115200 8N1, assigns GPIO17/18 as TX/RX, reads with `uart_read_bytes()`, and echoes the received bytes through `uart_write_bytes()`. The CI helper `.github/scripts/esp32s3-uart1-smoke.py` launches the pinned Espressif `esp-emu 0.51.0` UART1 TCP server, waits for the application-ready marker, connects a host-side mock device, sends a unique byte payload, requires the same bytes to be received back, and additionally requires a UART0 log line proving the firmware RX driver processed data. A socket response without the UART0 RX marker is not accepted as a pass.

This covers the UART1 RX/TX data path of this firmware and emulator version; it does not imply that every baud-rate corner case, UART interrupt path, GPIO matrix route, or all ESP32-S3 UARTs are fully modelled.


## Interactive runtime backend selection

The ESP32-S3 runtime monitor now accepts `backend=auto|esp-emu|qemu`. Auto mode selects a locally available `esp-emu` first, then falls back to the Espressif QEMU monitor when it is absent. Explicit `esp-emu` selection does not silently fall back: if the binary is missing the API returns the pinned installation command. QEMU remains a deliberate choice for its ROM/boot diagnostic path, and the runtime monitor labels its known GPIO/IOMUX readback limitation.

The adapter discovers the executable in this order: `ZETSIM_ESP_EMU`, `PATH`, then the repository-local ignored directory `.tools/esp-emu-0.51.0/`. The CI does not check the binary into Git. To install it locally on a supported POSIX host from the repository root:

```sh
curl -fsSL https://raw.githubusercontent.com/espressif/esp-emulator/v0.51.0/install.sh | sh -s -- --version 0.51.0 --bin-dir .tools/esp-emu-0.51.0 --force
```

Selecting `esp-emu` builds the selected ESP-IDF project, merges the flash image, then launches the merged binary and ELF used for trace/symbol information. This work runs in a worker thread so it does not block unrelated web requests. UART0 input in the monitor is forwarded to the running firmware; UART1 external-device communication has a separate CI loopback regression.


### Workbench selector and active engine display

The runtime monitor now offers `Auto`, `esp-emu`, and `QEMU` in the UI. Its live status identifies the engine that actually launched, rather than merely echoing the requested preference. The start, stop, and UART0 input operations run through worker threads so IDF build/merge preparation and process lifecycle locks do not stall the web event loop. A request using an unsupported backend is rejected before a process is launched.


### Windows host note

The official `esp-emu` README currently documents prebuilt native binaries for Linux x86_64/arm64 and macOS Apple Silicon, but does not list a native Windows binary. The local backend therefore does not suggest running the POSIX shell installer in PowerShell. On a Windows host with no compatible binary, Auto selects the existing Espressif QEMU/ESP-IDF path; an explicit esp-emu selection explains that the supported route is to run the project from WSL2 Ubuntu (including the ESP-IDF environment) or to use QEMU on Windows. The browser-hosted WASM emulator is an alternative for visual/manual experiments, but its hosted page does not provide local TCP networking and is not interchangeable with the native UART1 TCP test.


### Backend availability preflight

The UI calls `GET /api/esp32/runtime/backends` before launching a project. It reports whether the pinned `esp-emu` executable was found and whether the host has the ESP-IDF command, QEMU executable, and interactive console transport needed by the QEMU backend. Missing prerequisites include actionable reasons; this check does not start the emulator, compile firmware, or make a promise that the firmware itself will run successfully.
