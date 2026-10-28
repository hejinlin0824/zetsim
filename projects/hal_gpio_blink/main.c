/*
 * Beginner project: blink PA5 with ST's official STM32F1 HAL APIs.
 * Wiring: PA5 -> 330-ohm resistor -> LED anode; LED cathode -> GND.
 */
#include "stm32f1xx_hal.h"

#define BLINK_INTERVAL_MS 250U

int main(void)
{
    HAL_Init();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef led = {0};
    led.Pin = GPIO_PIN_5;
    led.Mode = GPIO_MODE_OUTPUT_PP;
    led.Pull = GPIO_NOPULL;
    led.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &led);

    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);

    while (1)
    {
        HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);
        HAL_Delay(BLINK_INTERVAL_MS);
    }
}

/* HAL's default 1ms time base advances from the SysTick interrupt. */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
