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
- **外设**：RCC/GPIO/EXTI/USART/TIM(8个)/ADC(3个)/DMA/SPI/I2C/DAC —— 按 RM0008 的可验证子集建模，精度边界见 [精度看板](docs/accuracy.md)
- **器件**：LED/按键/电位器/示波器/SSD1306 OLED，事件驱动
- **混合仿真**：内置 mini-SPICE（MNA+后向欧拉），PWM→RC滤波、LED 压降/限流可算
- **原理图画布（M8）**：像 Proteus 一样摆元件、连线、仿真——MCU 引脚、LED、电阻、电容、
 按键、电位器、GND/+3.3V、示波器探针；串阻 LED 的电流和 RC 结点电压由 SPICE 实时求解
- **验证**：pytest 回归覆盖指令/外设、DMA 与通信、原理图网表、GPIO 上下拉/开漏、ADC—SPICE 电压耦合、按键消抖与 RC 时间响应；GitHub Actions 在 Python 3.11/3.12 双版本运行

详细文档：[使用手册](使用手册.md) · [案例学习路线](docs/learning-path.md) · [精度看板](docs/accuracy.md) · [架构](ARCHITECTURE.md) · [寄存器速查](docs/registers.md)

## 安装

```bash
git clone https://github.com/hejinlin0824/zetsim.git
cd zetsim
python setup_env.py        # 一键：装 Python 依赖 + 检查/下载 arm-gcc（项目级 .toolchain/，不动系统）
python -m zetsim serve --firmware firmware/button_exti.hex
# 浏览器打开 http://127.0.0.1:8000 —— 点画布上的按键 SW1，LED 随中断翻转
```

没有 C 编译器的电脑直接跑 `setup_env.py`：它会把 xPack GNU Arm 下载解压到项目内 `.toolchain/`（已 gitignore），
编译时自动优先使用；无网络时也可 `winget install Arm.GnuArmEmbeddedToolchain` 装系统版。
跑测试：`pip install -e ".[dev]" && pytest`。

## 快速开始

```bash
python tools/gen_firmware.py       # （可选）重新生成演示固件到 firmware/
zetsim run firmware/hello_echo.hex --time 50ms --uart 1
zetsim serve                       # 浏览器打开 http://127.0.0.1:8000
```

## 写项目（边做边学）

在浏览器里直接写 C、编译、看板子跑——完整学习闭环：

1. 装一次编译器：`winget install Arm.GnuArmEmbeddedToolchain`（Linux 用发行版的 gcc-arm-none-eabi 包）
2. `zetsim serve` → 工具栏「✎ 项目」→ 选择项目 → 改代码 → **保存并编译运行**
3. 编译成功固件自动加载开跑；报错会带行号显示在编辑器下方

第一个项目 `projects/led_marquee`（8-LED 跑马灯）含四个带注释的教学文件：
`main.c`（业务逻辑）、`startup.c`（上电启动）、`stm32f103.h`（寄存器定义）、`link.ld`（内存布局）。
配套电路在工具栏「电路预设 → 8-LED 跑马灯」一键载入。命令行编译：`zetsim build projects/led_marquee`。

## 用自己的固件

用 Keil(armcc/armclang) 或 arm-none-eabi-gcc 为 STM32F103ZET6 编译，
把生成的 `.hex` 或 `.elf` 直接交给 zetsim。仿真器按 HSI 8MHz 启动
（固件里自行配 PLL 则时钟树跟随），复位向量从 0x08000000 读取。
