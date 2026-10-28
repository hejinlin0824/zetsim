"""Guard the vendored vendor CMSIS integration used by tutorial projects."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (
    "gpio_blink",
    "led_marquee",
    "exti_button",
    "uart_echo",
    "pwm_adc_control",
    "pwm_rc_filter",
)


def test_all_learning_projects_use_the_thin_cmsis_wrapper():
    for project in PROJECTS:
        wrapper = (ROOT / "projects" / project / "stm32f103.h").read_text(encoding="utf-8")
        assert '#include "stm32f1xx.h"' in wrapper
        assert "#define STM32F103xE" in wrapper
        assert "typedef struct" not in wrapper, f"{project} still hand-defines peripheral structures"


def test_official_st_device_and_arm_core_headers_are_present():
    device_dir = ROOT / "third_party" / "cmsis-device-f1" / "Include"
    core_dir = ROOT / "third_party" / "CMSIS_5" / "CMSIS" / "Core" / "Include"

    family = (device_dir / "stm32f1xx.h").read_text(encoding="utf-8")
    device = (device_dir / "stm32f103xe.h").read_text(encoding="utf-8")
    core = (core_dir / "core_cm3.h").read_text(encoding="utf-8")

    assert "#elif defined(STM32F103xE)" in family
    assert '#include "stm32f103xe.h"' in family
    assert "Copyright (c) 2017-2021 STMicroelectronics." in device
    assert "RCC_TypeDef" in device and "GPIO_TypeDef" in device
    assert "SysTick_Type" in core
    assert (ROOT / "third_party" / "cmsis-device-f1" / "LICENSE.md").is_file()
    assert (ROOT / "third_party" / "CMSIS_5" / "LICENSE.txt").is_file()


def test_build_helper_adds_both_official_cmsis_include_paths():
    source = (ROOT / "zetsim" / "build.py").read_text(encoding="utf-8")
    assert '"third_party" / "cmsis-device-f1" / "Include"' in source
    assert '"third_party" / "CMSIS_5" / "CMSIS" / "Core" / "Include"' in source
