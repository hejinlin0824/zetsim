from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HAL_ROOT = ROOT / "third_party" / "stm32f1xx-hal-driver"
HAL_PROJECT = ROOT / "projects" / "hal_gpio_blink"


def test_official_st_hal_sources_and_license_are_present() -> None:
    upstream = (HAL_ROOT / "UPSTREAM.md").read_text(encoding="utf-8")
    license_text = (HAL_ROOT / "LICENSE.md").read_text(encoding="utf-8")
    header = (HAL_ROOT / "Inc" / "stm32f1xx_hal_gpio.h").read_text(encoding="utf-8")
    legacy_header = (HAL_ROOT / "Inc" / "Legacy" / "stm32_hal_legacy.h").read_text(encoding="utf-8")
    source = (HAL_ROOT / "Src" / "stm32f1xx_hal_gpio.c").read_text(encoding="utf-8")

    assert "bd368aa335c529641d2e567574885e02deacc64a" in upstream
    assert "1.1.10" in upstream
    assert "Redistribution and use in source and binary forms" in license_text
    assert "STMicroelectronics" in header
    assert "STM32 HAL legacy" in legacy_header or "Legacy" in legacy_header or "Copyright" in legacy_header
    assert "HAL_GPIO_Init" in source
    assert "HAL_GPIO_TogglePin" in source


def test_hal_example_calls_library_apis_instead_of_registers() -> None:
    source = (HAL_PROJECT / "main.c").read_text(encoding="utf-8")
    for api in (
        "HAL_Init()",
        "__HAL_RCC_GPIOA_CLK_ENABLE()",
        "HAL_GPIO_Init(GPIOA, &led)",
        "HAL_GPIO_WritePin(",
        "HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5)",
        "HAL_Delay(BLINK_INTERVAL_MS)",
        "HAL_IncTick()",
    ):
        assert api in source, f"missing HAL API call: {api}"
    assert "GPIOA->CRL" not in source
    assert "REG32(" not in source
    assert "__asm" not in source


def test_builder_opts_into_official_hal_for_hal_projects_only() -> None:
    source = (ROOT / "zetsim" / "build.py").read_text(encoding="utf-8")
    assert 'project_dir / "stm32f1xx_hal_conf.h"' in source
    for token in (
        "stm32f1xx_hal.c",
        "stm32f1xx_hal_cortex.c",
        "stm32f1xx_hal_gpio.c",
        "system_stm32f1xx.c",
        "-DUSE_HAL_DRIVER",
        "str(hal_include)",
        'hal_include / "Legacy" / "stm32_hal_legacy.h"',
    ):
        assert token in source, f"HAL build integration missing: {token}"


def test_hal_startup_has_systick_vector_and_valid_linker_entry() -> None:
    startup = (HAL_PROJECT / "startup.c").read_text(encoding="utf-8")
    linker = (HAL_PROJECT / "link.ld").read_text(encoding="utf-8")
    assert "[15] = SysTick_Handler" in startup
    assert "[16 ... 75] = Default_Handler" in startup
    assert "ENTRY(Reset_Handler)" in linker
    assert "KEEP(*(.isr_vector))" in linker
