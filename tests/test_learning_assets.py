"""Regression tests for safe starter schematics and hands-on learning projects."""
from __future__ import annotations

from pathlib import Path

from zetsim.webapp import DEFAULT_SCHEMATIC, _led8_schematic

ROOT = Path(__file__).resolve().parents[1]
LEARNING_PROJECTS = (
    "gpio_blink",
    "led_marquee",
    "exti_button",
    "uart_echo",
    "pwm_adc_control",
    "pwm_rc_filter",
)


def _wire_pairs(schematic: dict) -> set[frozenset[tuple[str, str]]]:
    return {
        frozenset((tuple(wire["a"]), tuple(wire["b"])))
        for wire in schematic["wires"]
    }


def _wire(a: tuple[str, str], b: tuple[str, str]) -> frozenset[tuple[str, str]]:
    return frozenset((a, b))


def test_default_led_path_includes_current_limiting_resistor() -> None:
    schematic = DEFAULT_SCHEMATIC
    components = {component["id"]: component for component in schematic["components"]}
    wires = _wire_pairs(schematic)

    assert components["R_LED1"]["type"] == "resistor"
    assert components["R_LED1"]["props"]["ohms"] == 330
    assert _wire(("MCU", "PA5"), ("R_LED1", "1")) in wires
    assert _wire(("R_LED1", "2"), ("LED1", "A")) in wires
    assert _wire(("LED1", "K"), ("GND1", "G")) in wires
    assert _wire(("MCU", "PA5"), ("LED1", "A")) not in wires


def test_every_led_marquee_output_has_a_330_ohm_series_resistor() -> None:
    schematic = _led8_schematic()
    components = {component["id"]: component for component in schematic["components"]}
    wires = _wire_pairs(schematic)

    for index in range(8):
        resistor_id = f"R{index + 1}"
        led_id = f"LED{index + 1}"
        ground_id = f"GND{index + 1}"
        pin = f"PA{index}"

        assert components[resistor_id]["type"] == "resistor"
        assert components[resistor_id]["props"]["ohms"] == 330
        assert _wire(("MCU", pin), (resistor_id, "1")) in wires
        assert _wire((resistor_id, "2"), (led_id, "A")) in wires
        assert _wire((led_id, "K"), (ground_id, "G")) in wires
        assert _wire(("MCU", pin), (led_id, "A")) not in wires


def test_all_learning_projects_have_a_complete_buildable_template() -> None:
    required = ("main.c", "startup.c", "stm32f1xx_hal_conf.h", "link.ld", "README.md")
    for name in LEARNING_PROJECTS:
        project = ROOT / "projects" / name
        assert project.is_dir(), f"missing learning project: {name}"
        for filename in required:
            assert (project / filename).is_file(), f"{name} is missing {filename}"
        source = (project / "main.c").read_text(encoding="utf-8")
        assert '#include "stm32f1xx_hal.h"' in source
        assert "HAL_Init()" in source
        assert "int main(void)" in source


def test_exti_project_registers_irq6_in_the_vector_table() -> None:
    startup = (ROOT / "projects/exti_button/startup.c").read_text(encoding="utf-8")
    main = (ROOT / "projects/exti_button/main.c").read_text(encoding="utf-8")

    assert "[22] = EXTI0_IRQHandler" in startup
    assert "HAL_NVIC_EnableIRQ(EXTI0_IRQn)" in main
    assert "HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0)" in main
    assert "GPIO_MODE_IT_RISING" in main


def test_uart_project_uses_hal_uart_apis() -> None:
    main = (ROOT / "projects/uart_echo/main.c").read_text(encoding="utf-8")

    assert "HAL_UART_Init(&huart1)" in main
    assert "UART_MODE_TX_RX" in main
    assert "HAL_UART_Transmit(" in main
    assert "HAL_UART_Receive(" in main
    assert "USART1_DR" not in main


def test_adc_project_maps_sample_to_pwm_compare_register() -> None:
    main = (ROOT / "projects/pwm_adc_control/main.c").read_text(encoding="utf-8")

    assert "HAL_ADC_PollForConversion(&hadc1" in main
    assert "HAL_ADC_GetValue(&hadc1)" in main
    assert "__HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1," in main
    assert "DUTY_MIN + (sample * DUTY_SPAN) / 4095U" in main
    assert "#define PWM_ARR       99U" in main


def test_rc_project_uses_fixed_10khz_30_percent_pwm() -> None:
    main = (ROOT / "projects/pwm_rc_filter/main.c").read_text(encoding="utf-8")

    assert "#define PWM_PSC   7U" in main
    assert "#define PWM_ARR   99U" in main
    assert "#define PWM_DUTY  30U" in main
    assert "HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1)" in main
