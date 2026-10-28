/* 实战 01：GPIO 闪灯
 * 接线：MCU PA5 -> 330Ω -> LED 阳极；LED 阴极 -> GND。
 * 学习：RCC 时钟门控、CRL 四位引脚配置、SysTick 忙等延时。
 */
#include "stm32f103.h"

#define LED_PIN (1u << 5)
#define BLINK_MS 250u

static void delay_ms(uint32_t ms)
{
    /* HSI 默认 8MHz；此演示按当前教学模型换算。
     * SysTick LOAD 最大 24 位，单次延时需小于约 2.09s。
     */
    SysTick->LOAD = 8000u * ms - 1u;
    SysTick->VAL = 0;
    SysTick->CTRL = 0x5u;
    while ((SysTick->CTRL & (1u << 16)) == 0u) { }
    SysTick->CTRL = 0u;
}

int main(void)
{
    RCC->APB2ENR |= (1u << 2);                 /* GPIOA 时钟 */
    GPIOA->CRL = (GPIOA->CRL & ~(0xFu << 20)) | (0x2u << 20); /* PA5 推挽输出 */
    GPIOA->BRR = LED_PIN;

    while (1) {
        GPIOA->ODR ^= LED_PIN;
        delay_ms(BLINK_MS);
    }
}
