/* 实战 03：EXTI 外部中断按键（HAL 库函数版）
 * 接线：默认原理图 PA0 -> SW1；PA5 -> 330Ω -> LED -> GND。
 * 学习：HAL 下配置中断引脚（GPIO_MODE_IT_RISING）、NVIC 使能、
 *       EXTI 中断服务函数 → 清 pending → 回调函数的标准三段式。
 */
#include "stm32f1xx_hal.h"

#define LED_PIN GPIO_PIN_5

int main(void)
{
    HAL_Init();

    __HAL_RCC_GPIOA_CLK_ENABLE();
    /* EXTI 信号要经过 AFIO 路由到具体端口；
     * 上一版寄存器写的是 AFIO_EXTICR1，HAL 在 HAL_GPIO_Init 里写同一个寄存器，
     * 但 AFIO 的时钟必须自己开。 */
    __HAL_RCC_AFIO_CLK_ENABLE();

    /* 按键：GPIO_MODE_IT_RISING 一句话完成了上一版的四步——
     * AFIO_EXTICR1 路由到 Port A、EXTI_RTSR 选上升沿、EXTI_IMR 放行。
     * 教学模型约定：按键按下产生上升沿。 */
    GPIO_InitTypeDef button = {0};
    button.Pin   = GPIO_PIN_0;
    button.Mode  = GPIO_MODE_IT_RISING;   /* 上升沿触发外部中断 */
    button.Pull  = GPIO_NOPULL;           /* 教学模型内部有确定电平 */
    button.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &button);

    /* NVIC：设优先级并放行 EXTI0（IRQ 编号 6）。
     * 上一版的 NVIC_ISER0 |= (1u << 6) 现在由 HAL_NVIC_EnableIRQ 代劳。 */
    HAL_NVIC_SetPriority(EXTI0_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);

    /* LED：PA5 推挽输出，初始灭 */
    GPIO_InitTypeDef led = {0};
    led.Pin   = LED_PIN;
    led.Mode  = GPIO_MODE_OUTPUT_PP;
    led.Pull  = GPIO_NOPULL;
    led.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &led);
    HAL_GPIO_WritePin(GPIOA, LED_PIN, GPIO_PIN_RESET);

    while (1) {
        /* WFI：等中断。按下按键 → EXTI0 上升沿 → 进入 EXTI0_IRQHandler。
         * __WFI() 是 CMSIS 内建指令，替代上一版的内联汇编。 */
        __WFI();
    }
}

/* 中断服务函数：HAL 约定先清 pending 再回调。
 * HAL_GPIO_EXTI_IRQHandler 内部做的事就是上一版的 EXTI_PR = 1u（写 1 清除）。 */
void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);
}

/* 回调函数：清完 pending 后 HAL 把业务逻辑交到这里，我们只管翻转 LED。 */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == GPIO_PIN_0) {
        HAL_GPIO_TogglePin(GPIOA, LED_PIN);
    }
}

/* HAL 的 1ms 时基由 SysTick 中断推进（见 startup.c 向量表第 15 项）。 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
