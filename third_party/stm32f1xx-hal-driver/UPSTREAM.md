# STMicroelectronics STM32F1 HAL driver — pinned upstream

- Repository: https://github.com/STMicroelectronics/stm32f1xx-hal-driver
- Commit: `bd368aa335c529641d2e567574885e02deacc64a`
- Driver version: 1.1.10
- License: BSD 3-Clause; original upstream `LICENSE.md` is retained.

The HAL headers and C drivers were copied from the pinned upstream commit without edits. The unused `Src/stm32f1xx_hal_timebase_rtc_alarm_template.c` is intentionally omitted because its upstream blob did not pass transfer verification. LL drivers and legacy CAN compatibility files are outside this HAL-only integration.

The first zetsim project links only `stm32f1xx_hal.c`, `stm32f1xx_hal_cortex.c`, and `stm32f1xx_hal_gpio.c`, together with ST's CMSIS device system source. Other driver modules are present for later examples, but are not linked unless used.
