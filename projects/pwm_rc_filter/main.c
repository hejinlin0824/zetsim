/* 实战 06：固定占空比 PWM 驱动 RC 低通滤波
 * 接线：PA0 -> 1kΩ -> 节点；节点 -> 100nF -> GND；探针并接节点。
 * 学习：TIM2 PWM、τ=R*C、均值与纹波。
 */
#include "stm32f103.h"

#define REG32(addr) (*(volatile uint32_t *)(uintptr_t)(addr))
#define TIM2_CR1   REG32(0x40000000u)
#define TIM2_CCMR1 REG32(0x40000018u)
#define TIM2_CCER  REG32(0x40000020u)
#define TIM2_EGR   REG32(0x40000014u)
#define TIM2_PSC   REG32(0x40000028u)
#define TIM2_ARR   REG32(0x4000002Cu)
#define TIM2_CCR1  REG32(0x40000034u)

int main(void)
{
    RCC->APB2ENR |= (1u << 2); /* GPIOA clock */
    RCC->APB1ENR |= 1u;         /* TIM2 clock */
    GPIOA->CRL = (GPIOA->CRL & ~0xFu) | 0xBu; /* PA0 TIM2_CH1 AF push-pull */

    TIM2_CR1 = 0u;
    TIM2_PSC = 7u;
    TIM2_ARR = 99u;             /* 10kHz PWM */
    TIM2_CCR1 = 30u;             /* 30% duty */
    TIM2_CCMR1 = 0x0060u;        /* PWM mode 1 */
    TIM2_CCER = 1u;              /* CH1 output enabled */
    TIM2_EGR = 1u;
    TIM2_CR1 = 1u;

    /* 定时器硬件继续输出 PWM；CPU 休眠等待，便于观察硬件独立运行。 */
    while (1) {
        __asm volatile ("wfi");
    }
}
