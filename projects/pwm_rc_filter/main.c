/* 实战 06：固定占空比 PWM 驱动 RC 低通滤波（HAL 库函数版）
 * 接线：PA0 -> 1kΩ -> 节点；节点 -> 100nF -> GND；探针并接节点。
 * 学习：HAL_TIM PWM 配置三步曲（Init → ConfigChannel → Start）、
 *       τ=R*C、均值与纹波；定时器硬件独立于 CPU 运行。
 */
#include "stm32f1xx_hal.h"

static TIM_HandleTypeDef htim2;

/* 10kHz PWM @ 8MHz HSI：PSC 寄存器 = 7（÷8 → 1MHz 计数）、
 * ARR 寄存器 = 99（100 拍/周期）。HAL 的 Init 成员原样写入寄存器，不再减一。 */
#define PWM_PSC   7U
#define PWM_ARR   99U
#define PWM_DUTY  30U   /* 30% 占空比 → RC 节点均值约 0.99V（3.3V × 0.30） */

int main(void)
{
    HAL_Init();

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_TIM2_CLK_ENABLE();

    /* PA0：复用推挽，信号交给 TIM2_CH1（上一版手工填 CRL 0xB 位段） */
    GPIO_InitTypeDef io = {0};
    io.Pin   = GPIO_PIN_0;
    io.Mode  = GPIO_MODE_AF_PP;
    io.Pull  = GPIO_NOPULL;
    io.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &io);

    /* 第 1 步：时基（决定 PWM 频率）。HAL 的成员值原样写进 PSC/ARR 寄存器。 */
    htim2.Instance               = TIM2;
    htim2.Init.Prescaler         = PWM_PSC;       /* 分频 = PSC+1：8MHz ÷ 8 = 1MHz 计数 */
    htim2.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim2.Init.Period            = PWM_ARR;       /* 1MHz ÷ (99+1) = 10kHz              */
    htim2.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_PWM_Init(&htim2);

    /* 第 2 步：通道模式（决定波形形状），PWM 模式 1 + 30% 占空比 */
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode     = TIM_OCMODE_PWM1;
    oc.Pulse      = PWM_DUTY;               /* CCR1 = 30 */
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim2, &oc, TIM_CHANNEL_1);

    /* 第 3 步：启动（内部置 CCER.CC1E + CR1.CEN，波形开始输出） */
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);

    /* 定时器硬件继续输出 PWM；CPU 休眠等待，便于观察硬件独立运行。 */
    while (1) {
        __WFI();
    }
}

/* HAL 的 1ms 时基由 SysTick 中断推进（见 startup.c 向量表第 15 项）。 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
