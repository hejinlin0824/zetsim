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


## Snapshot API integration

- GET `/api/project/snapshot` exports the current STM32 circuit in the versioned project envelope.
- POST `/api/project/snapshot` validates and restores a versioned project. Invalid snapshots are rejected before replacing the active circuit.
- ESP32-S3 target metadata is registered, but its firmware continues through the dedicated ESP-IDF/QEMU workflow; it is not falsely routed into the STM32 schematic runtime.


## Wokwi architecture cross-check (design hypotheses, not compatibility claims)

The external review identifies three useful parallels. Treat these as design guidance to validate against zetsim's implementation, not as proof that zetsim already implements Wokwi's runtime or file format.

### 1. Schematic interchange boundary

zetsim's internal model remains `components + wires → union-find nets → pin/net binding`. Do not replace it wholesale with Wokwi's `diagram.json` contract. Add a separate importer/exporter adapter if interchange is needed, preserving unknown metadata where practical and validating all referenced part IDs and pin names before changing the active project.

The adapter must explicitly test the semantics of part attributes, rotation, visibility, and connection-routing tokens (including `v`, `h`, and `*`) before claiming compatibility. Internal canonical data and external interchange data have different responsibilities.

### 2. Runtime contract cross-check

Use this mapping as a review checklist:

| Wokwi-style concept in the review | zetsim contract to inspect | Required invariant |
| --- | --- | --- |
| `pinNames` | component registry pin metadata | one authoritative pin definition per component type |
| `onValueChange` subscriptions | net/device event propagation | a changed net notifies only relevant subscribers |
| `updated` dirty flag | device dirty-state / render invalidation | repeated unchanged values do not trigger redundant work |
| `sharedClock` | simulation scheduler and simulation-time clock | all devices in one simulation observe the same logical time |
| constructor receives clock, pins and attrs | device creation from registry/project data | device setup is deterministic and validated before stepping |

The review does not establish that each of these exact APIs exists in the upstream implementation or that zetsim currently matches their semantics. Before expanding analog behavior, add focused tests for event ordering, repeated-value suppression, deterministic step advancement, and invalid pin references. Keep digital logic authoritative; treat MNA/SPICE as a separately scoped analog layer.

### 3. ESP32-S3 boot smoke acceptance

ESP32-S3 remains a separate ESP-IDF + Espressif QEMU backend, not a schematic-device emulation shortcut. The other AI's ROM inventory, asset paths, and sample boot log are useful candidate fixtures, but they are not yet repository-local acceptance evidence.

For a reproducible smoke test, record:
- ESP-IDF/toolchain and QEMU binary versions (and the QEMU fork/source revision);
- required ROM/flash assets, their expected paths, and checksums where redistribution permits;
- the exact build and QEMU command lines, timeout, exit status, and captured UART output;
- a small set of stable boot markers, including reset reason when the selected firmware prints it;
- clear distinctions between “firmware built”, “QEMU process started”, “UART boot marker observed”, and “application reached its own ready marker”.

Avoid requiring a single hard-coded timestamp or an entire exact UART transcript when those lines vary by firmware or QEMU revision. The CI job should fail if a required asset is missing or the expected boot marker is not observed within the timeout.

### Follow-up implementation order

1. Verify the current ESP32-S3 CI smoke job and turn its observed output into a stable acceptance contract.
2. Add schema-adapter tests for import/export and round-trip preservation before implementing Wokwi `diagram.json` compatibility.
3. Add scheduler/net/device invariants as tests before adding more device types or analog models.
4. Evaluate `@wokwi/elements` in a thin rendering adapter/prototype first; do not couple its DOM/Web Component lifecycle directly to the backend or canonical project schema.
