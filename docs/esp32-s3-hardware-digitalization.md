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
