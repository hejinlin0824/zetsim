# 实战 05：ADC → PWM 闭环控制

## 接线
- MCU VDD → +3.3V；VSS → GND
- PA1 → 电位器 W（0..3.3V）
- PA0 → 探针 / LED 限流电阻网络

## 工作原理
`HAL_ADC_Init` 配置 ADC1 单通道连续转换；`HAL_ADC_ConfigChannel` 选择通道 1（PA1）；`HAL_ADC_PollForConversion` 等到 EOC 后用 `HAL_ADC_GetValue` 读出 12 位采样值，再经 `__HAL_TIM_SET_COMPARE` 写入 TIM2 通道 1 比较值。`htim2.Init.Prescaler=7、Period=99`（原样写进 PSC/ARR 寄存器），在 8MHz 定时器输入下目标 PWM 频率为 10kHz。这里的 PWM 占空比由真实固件寄存器写入控制，不是 UI 动画。真实硬件建议在启动前调用 `HAL_ADCEx_Calibration_Start` 校准；仿真器未建模校准位，可跳过。

## 动手任务
1. 编译运行并把探针接 PA0。
2. 慢慢拖动电位器，观察 PA1 电压与 PA0 PWM 占空比同步变化。
3. 把 `DUTY_MIN/DUTY_SPAN` 从 5/90 改成 10/70，解释限幅如何影响输出。
4. 固定 PA1 电压，在示波器上比较占空比稳定性。

## 验收
PA0 维持约 10kHz；低/中/高电位器输入对应不同占空比。若只有电压变化而占空比不变，检查 HAL_ADC_PollForConversion 返回值、HAL_ADC_GetValue 与 __HAL_TIM_SET_COMPARE 的写入链。
