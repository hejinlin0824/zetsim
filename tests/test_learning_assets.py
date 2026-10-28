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
    required = ("main.c", "startup.c", "stm32f103.h", "link.ld", "README.md")
    for name in LEARNING_PROJECTS:
        project = ROOT / "projects" / name
        assert project.is_dir(), f"missing learning project: {name}"
        for filename in required:
            assert (project / filename).is_file(), f"{name} is missing {filename}"
        source = (project / "main.c").read_text(encoding="utf-8")
        assert '#include "stm32f103.h"' in source
        assert "int main(void)" in source


def test_exti_project_registers_irq6_in_the_vector_table() -> None:
    startup = (ROOT / "projects/exti_button/startup.c").read_text(encoding="utf-8")
    main = (ROOT / "projects/exti_button/main.c").read_text(encoding="utf-8")

    assert "[22] = EXTI0_IRQHandler" in startup
    assert "NVIC_ISER0 |= (1u << 6)" in main
    assert "EXTI_PR = 1u" in main


def test_uart_project_uses_real_rxne_and_txe_status_flags() -> None:
    main = (ROOT / "projects/uart_echo/main.c").read_text(encoding="utf-8")

    assert "(1u << 7)" in main  # TXE
    assert "(1u << 5)" in main  # RXNE
    assert "USART1_DR" in main


def test_adc_project_maps_sample_to_pwm_compare_register() -> None:
    main = (ROOT / "projects/pwm_adc_control/main.c").read_text(encoding="utf-8")

    assert "ADC1_DR" in main
    assert "TIM2_CCR1 = 5u + (sample * 90u) / 4095u" in main
    assert "TIM2_ARR = 99u" in main


def test_rc_project_uses_fixed_10khz_30_percent_pwm() -> None:
    main = (ROOT / "projects/pwm_rc_filter/main.c").read_text(encoding="utf-8")

    assert "TIM2_PSC = 7u" in main
    assert "TIM2_ARR = 99u" in main
    assert "TIM2_CCR1 = 30u" in main
