/* 实战 01：GPIO 闪灯（HAL 库函数版）
 * 接线：MCU PA5 -> 330Ω -> LED 阳极；LED 阴极 -> GND。
 * 学习：HAL 初始化框架、外设时钟宏、HAL_GPIO_Init 输出配置、HAL_Delay 毫秒延时。
 */
#include "stm32f1xx_hal.h"

#define LED_PIN           GPIO_PIN_5
#define BLINK_MS          100U

int main(void)
{
    /* HAL_Init：复位 HAL 状态、配置 NVIC 优先级分组、把 SysTick 配成 1ms 中断。
     * 之后的 HAL_Delay 全靠这个 1ms 时基，不再需要手写 SysTick 寄存器。 */
    HAL_Init();

    /* 外设时钟：库函数版照样绕不开 RCC。
     * __HAL_RCC_GPIOA_CLK_ENABLE() 是宏，展开后就是往
     * RCC_APB2ENR 的 bit2 写 1——与上一版寄存器写法等价。 */
    __HAL_RCC_GPIOA_CLK_ENABLE();

    /* GPIO 初始化从“手工填 4 位配置”变成“填结构体”：
     * HAL_GPIO_Init 内部替你算 CRL/CRH 的位段。 */
    GPIO_InitTypeDef led = {0};
    led.Pin   = LED_PIN;              /* PA5                 */
    led.Mode  = GPIO_MODE_OUTPUT_PP;  /* 推挽输出            */
    led.Pull  = GPIO_NOPULL;          /* 输出模式不用上下拉  */
    led.Speed = GPIO_SPEED_FREQ_LOW;  /* 2MHz，闪灯足够      */
    HAL_GPIO_Init(GPIOA, &led);

    HAL_GPIO_WritePin(GPIOA, LED_PIN, GPIO_PIN_RESET); /* 先灭灯 */

    while (1) {
        HAL_GPIO_TogglePin(GPIOA, LED_PIN); /* 翻转电平：内部读 ODR 异或后写回 */
        HAL_Delay(BLINK_MS);                /* 忙等 BLINK_MS 毫秒（SysTick 时基） */
    }
}

/* HAL 的 1ms 时基由 SysTick 中断推进；
 * 函数名必须和向量表第 15 项一致（见 startup.c）。 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
