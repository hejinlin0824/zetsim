/* 实战 05：电位器 ADC 控制 PWM 亮度
 * PA0 = TIM2_CH1 PWM 输出；PA1 = ADC1_IN1 电位器输入。
 * 改动的不是网页 LED 状态，而是实际写入 TIM2_CCR1 的比较值。
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

#define ADC1_SR    REG32(0x40012400u)
#define ADC1_CR2   REG32(0x40012408u)
#define ADC1_SQR1  REG32(0x4001242Cu)
#define ADC1_SQR3  REG32(0x40012434u)
#define ADC1_DR    REG32(0x4001244Cu)

static void pwm_init(void)
{
    /* PA0：复用推挽输出；PA1：模拟输入 */
    GPIOA->CRL = (GPIOA->CRL & ~0xFFu) | 0x0Bu;
    TIM2_CR1 = 0u;
    TIM2_PSC = 7u;
    TIM2_ARR = 99u;          /* (8MHz / (7+1)) / (99+1) = 10kHz */
    TIM2_CCR1 = 5u;
    TIM2_CCMR1 = 0x0060u;    /* CH1 PWM mode 1 */
    TIM2_CCER = 1u;           /* enable CH1 */
    TIM2_EGR = 1u;            /* update generation */
    TIM2_CR1 = 1u;
}
static void adc_init(void)
{
    ADC1_SQR1 = 0u;            /* regular sequence length = 1 */
    ADC1_SQR3 = 1u;            /* channel 1 = PA1 */
    ADC1_CR2 = 1u;             /* power on */
    ADC1_CR2 = (1u << 30) | (1u << 1) | 1u; /* SWSTART | CONT | ADON */
}
int main(void)
{
    RCC->APB2ENR |= (1u << 2) | (1u << 9); /* GPIOA + ADC1 */
    RCC->APB1ENR |= 1u;                    /* TIM2 */
    pwm_init();
    adc_init();

    while (1) {
        if (ADC1_SR & (1u << 1)) {         /* EOC：转换完成 */
            uint32_t sample = ADC1_DR & 0x0FFFu;
            /* 映射到 5%..95%，避免输出长期贴在 0% 或 100%。 */
            TIM2_CCR1 = 5u + (sample * 90u) / 4095u;
        }
    }
}
