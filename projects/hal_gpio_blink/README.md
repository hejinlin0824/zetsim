# HAL GPIO 闪灯：先学库函数

这个工程直接使用 ST 官方 STM32F1 HAL 驱动，不是手写的同名 API 封装。

- `HAL_Init()`：初始化 HAL 和默认的 1ms 系统 tick。
- `__HAL_RCC_GPIOA_CLK_ENABLE()`：打开 GPIOA 外设时钟。
- `HAL_GPIO_Init()`：把 PA5 配置为推挽输出。
- `HAL_GPIO_TogglePin()`：翻转 PA5 电平。
- `HAL_Delay(250)`：等待约 250 毫秒；时间基准由 `SysTick_Handler` 中的 `HAL_IncTick()` 推进。

在仓库根目录运行：

```powershell
python -m zetsim build projects/hal_gpio_blink
python -m zetsim run projects/hal_gpio_blink/firmware.hex --time 520ms --trace-gpio
```

接线：PA5 -> 330Ω 电阻 -> LED -> GND。先看默认效果，再将 `BLINK_INTERVAL_MS` 改成 `100U` 或 `500U` 并重新编译。

真实板卡工程应使用芯片/板卡包提供的标准启动文件，并根据实际硬件核对时钟、向量表和接线。本例的 C 启动文件是用于 zetsim 教学链接布局的最小实现。
