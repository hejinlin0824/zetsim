/* ============================================================
 * 项目一：8-LED 跑马灯（HAL 库函数版）
 *
 * 电路连接（在网页原理图里照着连）：
 *     PA0..PA7 → 各自的 330Ω 限流电阻 → 对应 LED 正极
 *     所有 LED 负极 → GND
 *     限流电阻用于降低 LED 电流；不要把教学仿真的简化接法照搬到真实硬件。
 *
 * 学习目标：
 *   1. HAL_Init / __HAL_RCC_GPIOA_CLK_ENABLE：框架入口与外设时钟
 *   2. 一次 GPIO_Init 配 8 个脚（Pin 成员是掩码，可以按位或）
 *   3. HAL_GPIO_WritePin 逐脚点亮 + HAL_Delay 精确节拍
 * ============================================================ */
#include "stm32f1xx_hal.h"

/* 8 个灯接在 PA0~PA7。GPIO_PIN_x 本身就是 (1u << x) 的位掩码，
 * 多个脚可以按位或后一次交给 HAL_GPIO_Init。 */
static const uint16_t led_pins[8] = {
    GPIO_PIN_0, GPIO_PIN_1, GPIO_PIN_2, GPIO_PIN_3,
    GPIO_PIN_4, GPIO_PIN_5, GPIO_PIN_6, GPIO_PIN_7,
};

/* 一步走多快（毫秒）。改小它，灯跑得更快。*/
#define STEP_MS 100U

/* ---- 初始化：开时钟 + 配引脚 ---- */
static void led_init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();   /* 不开时钟写 GPIOA 全无效——新手最常踩的坑 */

    GPIO_InitTypeDef led = {0};
    led.Pin   = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2 | GPIO_PIN_3 |
                GPIO_PIN_4 | GPIO_PIN_5 | GPIO_PIN_6 | GPIO_PIN_7;
    led.Mode  = GPIO_MODE_OUTPUT_PP;  /* 8 个脚全部推挽输出 */
    led.Pull  = GPIO_NOPULL;
    led.Speed = GPIO_SPEED_FREQ_LOW;  /* HAL 内部填成 CRL = 0x22222222 */
    HAL_GPIO_Init(GPIOA, &led);
}

/* ---- 主函数：上电后 C 世界的入口 ---- */
int main(void)
{
    uint32_t i = 0;

    HAL_Init();      /* 1ms SysTick 时基，供 HAL_Delay 使用 */
    led_init();

    /* 超级循环（super loop）：裸机程序永不返回 */
    while (1)
    {
        HAL_GPIO_WritePin(GPIOA, led_pins[i], GPIO_PIN_SET);     /* 点亮第 i 个 */
        HAL_Delay(STEP_MS);                                      /* 停留一会儿  */
        HAL_GPIO_WritePin(GPIOA, led_pins[i], GPIO_PIN_RESET);   /* 熄灭它      */
        i++;                                                     /* 挪到下一个灯 */
        if (i >= 8)                                              /* 0→1→…→7→0  */
            i = 0;                                               /* （避免取余） */
    }
}

/* HAL 的 1ms 时基由 SysTick 中断推进（见 startup.c 向量表第 15 项）。 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
