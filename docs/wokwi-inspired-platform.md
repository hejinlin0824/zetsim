# Wokwi-inspired platform improvements (P0/P1)

This implementation deliberately supports only **STM32F103ZET6** and **ESP32-S3**. It does not add AVR or RP2040 emulation engines.

## P0 — versioned project model
The versioned zetsim.json envelope contains:
- schema_version: migration gate for future schema changes;
- target: stm32f103zet6 or esp32s3;
- files: project-owned text files;
- circuit: existing components / wires payload, retained for compatibility;
- simulation: project-level simulation settings.

The zetsim.project module validates, serializes and loads this envelope. Legacy circuit adapters bridge the existing web schematic contract; the current UI payload is not silently changed.

## P0 — declarative component registry
zetsim.component_registry is the single source for component pins, labels, renderer keys, capabilities and property metadata. The legacy PIN_DEFS mapping is generated from it so current validation remains compatible. Metadata does not claim a component has a physically complete model.

## P0 — deterministic local build cache
The cache key includes compiler identity/version, command flags, project source/header/linker inputs and relevant CMSIS/HAL source trees. Entries live under .zetsim/cache/build/ and restore only when both ELF and HEX exist. Changes to source, headers, linker scripts, HAL/CMSIS inputs, target flags, or compiler version invalidate the key.

## P1 — event observation
The existing EventBus already timestamps events in simulation nanoseconds and supports wildcard subscriptions. Keep it as the shared source for UI, CLI, and automated checks. The event log is bounded; observability features should consume event snapshots rather than scrape UI state.

## Open-source reuse policy
Evaluate assets by their actual license and integration fit. Private/internal use is not a blanket exemption from license conditions, especially for GPL-family code and redistribution. This change reuses architectural ideas and does not vendor Wokwi code or introduce an unreviewed dependency. Reconsider @wokwi/elements only after confirming its exact license/version and whether its Lit/Web Component renderers fit the existing static workbench.
