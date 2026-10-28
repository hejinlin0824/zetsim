# 实战 03：外部中断按键

## 信号链
SW1 → PA0 输入 → EXTI0 边沿检测 → NVIC IRQ6 → EXTI0_IRQHandler → PA5 LED 翻转。

## 重点
- GPIO 输入模式和 EXTI 不是同一层配置。
- AFIO_EXTICR1 选择 EXTI0 来源端口。
- EXTI_IMR 决定是否放行；RTSR/FTSR 决定触发边沿。
- 中断处理函数结束前必须清除 EXTI_PR 的 pending 位。
- `startup.c` 必须把 IRQ6 的处理函数放进向量表第 22 项。

## 动手任务
1. 按下、松开 SW1 五次，确认 LED 对应翻转五次。
2. 暂时注释 NVIC_ISER0 的使能，比较按键是否还能触发 ISR。
3. 暂时注释 EXTI_PR 清除语句，观察 pending 中断的行为变化（完成后恢复）。

## 验收
编译成功；运行时按键每次按下触发一次；复位后仍能继续触发。
