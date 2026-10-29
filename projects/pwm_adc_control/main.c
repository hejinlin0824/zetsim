/* 实战 05：电位器 ADC 控制 PWM 亮度（HAL 库函数版）
 * PA0 = TIM2_CH1 PWM 输出；PA1 = ADC1_IN1 电位器输入。
 * 改动的不是网页 LED 状态，而是 TIM2 通道 1 的比较值（CCR1）。
 */
#include "stm32f1xx_hal.h"

/* 一个外设一个句柄：TIM2 和 ADC1 各一个 */
static TIM_HandleTypeDef htim2;
static ADC_HandleTypeDef hadc1;

/* 10kHz PWM @ 8MHz HSI：PSC 寄存器 = 7（÷8 → 1MHz 计数）、
 * ARR 寄存器 = 99（100 拍/周期）。HAL 的 Init 成员原样写入寄存器，不再减一。 */
#define PWM_PSC       7U
#define PWM_ARR       99U
/* 占空比下限/上限：映射到 5%..95%，避免输出长期贴在 0% 或 100%。 */
#define DUTY_MIN      5U
#define DUTY_SPAN     90U

static void pwm_init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_TIM2_CLK_ENABLE();

    /* PA0：复用推挽，信号交给 TIM2_CH1 */
    GPIO_InitTypeDef io = {0};
    io.Pin   = GPIO_PIN_0;
    io.Mode  = GPIO_MODE_AF_PP;
    io.Pull  = GPIO_NOPULL;
    io.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &io);

    /* 时基：prescaler + 自动重装，算式写在注释里，10kHz 一眼可查。
     * HAL 的成员值原样写进 PSC/ARR 寄存器。 */
    htim2.Instance               = TIM2;
    htim2.Init.Prescaler         = PWM_PSC;       /* 分频 = PSC+1：8MHz ÷ 8 = 1MHz 计数 */
    htim2.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim2.Init.Period            = PWM_ARR;       /* 1MHz ÷ (99+1) = 10kHz              */
    htim2.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_PWM_Init(&htim2);

    /* 通道：PWM 模式 1（计数值 < CCR1 输出高），初始占空比 5% */
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode     = TIM_OCMODE_PWM1;
    oc.Pulse      = 5U;                       /* CCR1 初值 */
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim2, &oc, TIM_CHANNEL_1);

    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1); /* 内部置 CCER.CC1E + CR1.CEN */
}

static void adc_init(void)
{
    __HAL_RCC_ADC1_CLK_ENABLE();

    /* PA1：模拟输入（上一版 CRL 填 0x0 现在由 HAL 代劳） */
    GPIO_InitTypeDef io = {0};
    io.Pin  = GPIO_PIN_1;
    io.Mode = GPIO_MODE_ANALOG;
    io.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &io);

    /* 单通道连续转换、软件触发、右对齐 */
    hadc1.Instance                   = ADC1;
    hadc1.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc1.Init.ScanConvMode          = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode    = ENABLE;   /* 转完自动开始下一次 */
    hadc1.Init.NbrOfConversion       = 1U;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    HAL_ADC_Init(&hadc1);

    /* 规则序列第 1 个 = 通道 1（PA1），采样时间 1.5 周期 */
    ADC_ChannelConfTypeDef cfg = {0};
    cfg.Channel      = ADC_CHANNEL_1;
    cfg.Rank         = ADC_REGULAR_RANK_1;
    cfg.SamplingTime = ADC_SAMPLETIME_1CYCLE_5;
    HAL_ADC_ConfigChannel(&hadc1, &cfg);

    /* 真实硬件建议先跑 HAL_ADCEx_Calibration_Start() 做出厂式校准；
     * zetsim 的教学模型未建模校准位（CAL），跳过不影响结果。 */
    HAL_ADC_Start(&hadc1);   /* 置 ADON + SWSTART，连续模式开始持续转换 */
}

int main(void)
{
    HAL_Init();
    pwm_init();
    adc_init();

    while (1) {
        /* 等一次转换完成（EOC）。连续模式下 EOC 会不断置起。 */
        if (HAL_ADC_PollForConversion(&hadc1, 10U) == HAL_OK) {
            const uint32_t sample = HAL_ADC_GetValue(&hadc1); /* 0..4095 */
            /* 映射到 5%..95%：低采样 → 暗，高采样 → 亮。 */
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1,
                                  DUTY_MIN + (sample * DUTY_SPAN) / 4095U);
        }
    }
}

/* HAL 的 1ms 时基由 SysTick 中断推进（见 startup.c 向量表第 15 项）。 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
