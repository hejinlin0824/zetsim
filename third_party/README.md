# Vendored CMSIS headers

This directory contains upstream CMSIS headers used by the six zetsim C learning
projects. The device register definitions are sourced from official upstream
repositories; the project's `projects/*/stm32f103.h` files are compatibility
wrappers only and no longer define peripheral register structures by hand.

## STMicroelectronics STM32F1 device package

- Upstream: https://github.com/STMicroelectronics/cmsis-device-f1
- Pinned upstream commit: `c8e9a4a4f16b6d2cb2a2083cbe5161025280fb22`
- Files vendored: `stm32f1xx.h`, `stm32f103xe.h`, `system_stm32f1xx.h`
- License: Apache-2.0; copy of upstream `License.md` is included as `cmsis-device-f1/LICENSE.md`

The exact part STM32F103ZET6 uses ST's official high-density 512-KB variant
selection macro `STM32F103xE`. The CMSIS device header is officially named
`stm32f103xe.h`; ST does not name this header after the full `ZET6` ordering
code. The project wrapper defines the variant macro before including
`stm32f1xx.h`, which then includes the real device header.

## ARM CMSIS Core

- Upstream: https://github.com/ARM-software/CMSIS_5
- Pinned upstream commit: `55b19837f5703e418ca37894d5745b1dc05e4c91`
- Files vendored: `core_cm3.h`, `cmsis_compiler.h`, `cmsis_version.h`,
  `cmsis_gcc.h`, `mpu_armv7.h`
- License: Apache-2.0; copy of upstream `LICENSE.txt` is included here as `CMSIS_5/LICENSE.txt`

## Build integration

`zetsim/build.py` adds both official include directories when building any
`projects/<name>` project. The examples still include `stm32f103.h` to keep
their beginner-friendly and stable project layout, but RCC/GPIO/SysTick types,
register offsets, bit definitions and memory-mapped peripheral addresses come
from the upstream CMSIS files above. No ST HAL driver is included; the lessons
use direct CMSIS register access.
