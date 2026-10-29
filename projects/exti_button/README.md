# 实战 03：外部中断按键

## 信号链
SW1 → PA0 输入 → EXTI0 边沿检测 → NVIC IRQ6 → EXTI0_IRQHandler → PA5 LED 翻转。

## 重点
- `GPIO_MODE_IT_RISING` 一次完成“输入 + 上升沿中断”：HAL_GPIO_Init 内部写 AFIO_EXTICR1（来源端口）、EXTI_RTSR（边沿）和 EXTI_IMR（放行）。
- AFIO 时钟要自己开：`__HAL_RCC_AFIO_CLK_ENABLE()`。
- `HAL_NVIC_EnableIRQ(EXTI0_IRQn)` 放行 IRQ6。
- 中断处理函数里 `HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0)` 先清 EXTI_PR pending 位，再调用 `HAL_GPIO_EXTI_Callback`。
- `startup.c` 必须把 EXTI0 的处理函数放进向量表第 22 项（16 + IRQ6）。

## 动手任务
1. 按下、松开 SW1 五次，确认 LED 对应翻转五次。
2. 暂时注释 `HAL_NVIC_EnableIRQ(EXTI0_IRQn)`，比较按键是否还能触发 ISR。
3. 暂时把 `HAL_GPIO_EXTI_Callback` 改成空函数，观察清 pending 与业务回调的分工（完成后恢复）。

## 验收
编译成功；运行时按键每次按下触发一次；复位后仍能继续触发。
