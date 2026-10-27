# zetsim — STM32F103ZET6 个人仿真器

把"Keil 编译 → 加载固件 → 芯片真跑代码 → 引脚联动 → 交互调试"的 Proteus 式体验，
装进一个纯 Python、零外部 DLL、完全自包含的工具里。

```
zetsim run firmware/blink.hex --time 500ms     # 无头跑固件
zetsim serve                                    # 打开浏览器仪表盘
```

- **CPU**：Unicorn（QEMU TCG）Cortex-M3 指令级仿真，运行真实 Keil/GCC 编译的 `.hex/.elf`
- **异常引擎**：自研 ARMv7-M 异常入口/出口（压栈、EXC_RETURN、抢占、尾链、PendSV/SVC），
  通过了"FreeRTOS 式双任务上下文切换"期末考试
- **外设**：RCC/GPIO/EXTI/USART/TIM(8个)/ADC(3个)/DMA/SPI/I2C/DAC —— 行为按 RM0008 建模
- **器件**：LED/按键/电位器/示波器/SSD1306 OLED，事件驱动
- **混合仿真**：内置 mini-SPICE（MNA+后向欧拉），PWM→RC滤波、LED 压降/限流可算
- **原理图画布（M8）**：像 Proteus 一样摆元件、连线、仿真——MCU 引脚、LED、电阻、电容、
 按键、电位器、GND/+3.3V、示波器探针；串阻 LED 的电流和 RC 结点电压由 SPICE 实时求解
- **验证**：35 项 pytest（汇编器执行预言 + 固件功能断言 + SVD 寄存器地图交叉验证）

详细文档：[使用手册](使用手册.md) · [精度看板](docs/accuracy.md) · [架构](ARCHITECTURE.md) · [寄存器速查](docs/registers.md)

## 安装

```bash
git clone https://github.com/hejinlin0824/zetsim.git
cd zetsim
pip install -e .                                    # 安装依赖（Python ≥3.10）
python -m zetsim serve --firmware firmware/button_exti.hex
# 浏览器打开 http://127.0.0.1:8000 —— 点画布上的按键 SW1，LED 随中断翻转
```

演示固件已随仓库提供（`firmware/*.hex`），无需编译器。跑测试：`pip install -e ".[dev]" && pytest`。

## 快速开始

```bash
python tools/gen_firmware.py       # （可选）重新生成演示固件到 firmware/
zetsim run firmware/hello_echo.hex --time 50ms --uart 1
zetsim serve                       # 浏览器打开 http://127.0.0.1:8000
```

## 用自己的固件

用 Keil(armcc/armclang) 或 arm-none-eabi-gcc 为 STM32F103ZET6 编译，
把生成的 `.hex` 或 `.elf` 直接交给 zetsim。仿真器按 HSI 8MHz 启动
（固件里自行配 PLL 则时钟树跟随），复位向量从 0x08000000 读取。
