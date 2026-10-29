# 实战 02：8 路 LED 跑马灯

## 目标
用一个真正可编译的裸机 C 工程学习 HAL 下 GPIO 多路输出、GPIO_PIN_x 位掩码、HAL_Delay 节拍和简单的超级循环。

## 接线
- MCU VDD → +3.3V；VSS → GND
- PA0..PA7 分别经过独立 330Ω 限流电阻后连接 LED1..LED8 阳极
- 各 LED 阴极连接 GND

## 核心代码
- `__HAL_RCC_GPIOA_CLK_ENABLE()`：打开 GPIOA 的外设时钟（展开后就是 RCC_APB2ENR bit2）。
- 一次 `HAL_GPIO_Init(GPIOA, &led)`，`led.Pin` 为 8 个 GPIO_PIN_x 的按位或：PA0..PA7 全部推挽输出。
- `led_pins[i]`：用 GPIO_PIN_x 位掩码选择当前点亮的 LED。
- `HAL_Delay(STEP_MS)`：基于 HAL 1ms SysTick 时基等待指定时间。

## 动手任务
1. 打开浏览器的「案例库」并选择 8 路 LED 跑马灯。
2. 将电路载入原理图，再打开 `led_marquee` C 项目。
3. 把 `STEP_MS` 从 100 改为 60，使用 Ctrl+S 保存并使用 Ctrl+Enter 编译运行。
4. 把 60 改为 200，比较快、慢两种效果。
5. 进阶：把循环顺序改为倒序；完成后确认每路 LED 仍由独立限流电阻驱动。

## 验收
- 编译成功并生成 `firmware.hex`。
- 8 个 LED 依次点亮，调整 STEP_MS 可观察到速度变化。
- 电路包含 8 个独立的 330Ω 串联电阻；布线检查没有 LED 直接驱动警告。
