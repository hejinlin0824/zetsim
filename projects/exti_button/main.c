/* 实战 03：EXTI 外部中断按键
 * 接线：默认原理图 PA0 -> SW1；PA5 -> 330Ω -> LED -> GND。
 * 学习：GPIO 输入、AFIO 路由、EXTI 边沿、NVIC 向量表、pending 清除。
 */
#include "stm32f103.h"

#define REG32(addr) (*(volatile uint32_t *)(uintptr_t)(addr))
#define AFIO_EXTICR1 REG32(0x40010008u)
#define EXTI_IMR     REG32(0x40010400u)
#define EXTI_RTSR    REG32(0x40010408u)
#define EXTI_FTSR    REG32(0x4001040Cu)
#define EXTI_PR      REG32(0x40010414u)
#define NVIC_ISER0   REG32(0xE000E100u)
#define LED_PIN      (1u << 5)

void EXTI0_IRQHandler(void)
{
    GPIOA->ODR ^= LED_PIN;
    EXTI_PR = 1u;                 /* 写 1 清 EXTI0 pending */
}

int main(void)
{
    RCC->APB2ENR |= (1u << 0) | (1u << 2); /* AFIO + GPIOA */
    GPIOA->CRL = (GPIOA->CRL & ~((0xFu << 0) | (0xFu << 20)))
               | 0x4u | (0x2u << 20);    /* PA0 浮空输入；PA5 推挽输出 */
    GPIOA->BRR = LED_PIN;

    AFIO_EXTICR1 &= ~0xFu;        /* EXTI0 路由到 Port A */
    EXTI_PR = 1u;                 /* 清旧标志 */
    EXTI_IMR |= 1u;               /* 放行 EXTI0 */
    EXTI_RTSR |= 1u;              /* 教学模型按键按下产生上升沿 */
    EXTI_FTSR &= ~1u;
    NVIC_ISER0 |= (1u << 6);      /* EXTI0_IRQn = 6 */

    while (1) {
        __asm volatile ("wfi");
    }
}
