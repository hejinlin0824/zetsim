# zetsim — STM32F103ZET6 个人仿真器

把“Keil 编译 → 加载固件 → 芯片真跑代码 → 引脚联动 → 交互调试”的 Proteus 式体验，
装进一个纯 Python、零外部 DLL、完全自包含的工具里。

    zetsim run firmware/blink.hex --time 500ms     # 无头跑固件
    zetsim serve                                    # 打开浏览器仪表盘

- **CPU**：Unicorn（QEMU TCG）Cortex-M3 指令级仿真，运行真实 Keil/GCC 编译的 .hex/.elf
- **异常引擎**：自研 ARMv7-M 异常入口/出口（压栈、EXC_RETURN、抢占、尾链、PendSV/SVC），通过 FreeRTOS 式双任务上下文切换测试
- **外设**：RCC/GPIO/EXTI/USART/TIM/ADC/DMA/SPI/I2C/DAC —— 按 RM0008 的可验证子集建模，精度边界见 [精度看板](docs/accuracy.md)
- **器件**：LED/按键/电位器/示波器/SSD1306 OLED，事件驱动
- **混合仿真**：内置 mini-SPICE（MNA+后向欧拉），PWM→RC 滤波、LED 压降/限流可算
- **原理图画布**：像 Proteus 一样摆元件、连线、仿真；探针记录网络电压
- **学习案例库**：6 个循序案例（GPIO、跑马灯、EXTI、USART、ADC→PWM、RC 滤波），每个案例提供接线表、代码阅读点、实操任务与验收标准
- **布线检查**：检查 MCU 供电、无效/重复导线、悬空端子和常见 LED 限流问题；属于教学性基础检查，不替代完整 ERC/DRC
- **C 项目工作台**：6 个独立可编辑项目，支持保存、编译、未保存提醒和编译日志

## 学习与测试文档

- **[手把手学习教程](docs/learning-path.md)**：从环境准备开始，逐课阅读真实源码、改动参数、编译运行、观察现象并排查问题。建议初学者按 GPIO → 跑马灯 → EXTI → USART → ADC/PWM → RC 的顺序学习。
- **[Windows 实机验收提示词](docs/windows-acceptance-prompt.md)**：可以直接交给测试同事执行；包括测试环境、自动化测试、六个案例、编辑器、防误操作、RC/LED 数值与性能、Console/Network 和最终报告模板。
- [使用手册](使用手册.md)：安装、上手、工作台和 CLI 参考。
- [案例学习路线](docs/learning-path.md)：每课操作及源码导航。
- [精度看板](docs/accuracy.md)：已测能力、简化项和精度边界。
- [总体架构](ARCHITECTURE.md)：模块分层与关键调用链。
- [寄存器速查](docs/registers.md)：由 SVD 生成的寄存器信息。

## 安装与运行

在仓库根目录执行：

    python setup_env.py
    python -m pip install -e ".[dev]"
    python -m zetsim serve

然后浏览器打开 http://127.0.0.1:8000。Windows 若使用项目虚拟环境，请先激活该环境。

若尚未准备 ARM C 编译器，setup_env.py 会尝试准备项目级工具链（保存在 gitignore 管理的目录，不修改系统安装）；无网络时，可按团队环境安装 Arm GNU Toolchain。已有 HEX 可以在没有 C 编译器时用于快速观察，但改 C 后重新构建需要工具链。

CLI 示例：

    python -m zetsim run firmware/hello_echo.hex --time 50ms --uart 1
    python -m zetsim run firmware/blink.hex --time 2s --trace-gpio
    python -m zetsim build projects/led_marquee
    python -m pytest tests/ -q

## 跟着项目学 C 与 MCU

推荐第一次从 projects/gpio_blink/main.c 开始，不要从整个仓库开始通读。先读 main.c，再在 stm32f103.h 中寻找 RCC、GPIOA 和 SysTick 的寄存器定义。按照教程只改一个参数，保存、编译、运行，随后记录 LED 与 PA5 探针的变化。

六个可编辑 C 项目位于 projects/：

| 工程 | 学习重点 |
|---|---|
| gpio_blink | RCC、GPIO 输出、SysTick 延时 |
| led_marquee | 位掩码、循环、8 路 GPIO |
| exti_button | EXTI、NVIC、中断向量与 pending 清除 |
| uart_echo | USART1、TXE/RXNE、数据寄存器 |
| pwm_adc_control | ADC 采样值控制 TIM2 PWM 占空比 |
| pwm_rc_filter | 10kHz PWM、RC 时间常数、平均电压和纹波 |

每个工程都有 main.c、startup.c、stm32f103.h 与 link.ld。main.c 讲业务逻辑；startup.c 处理复位和向量表；stm32f103.h 描述寄存器地址；link.ld 决定 Flash 与 RAM 布局。

## 验证

自动回归测试：

    python -m pytest tests/ -q

GitHub Actions 在 Python 3.11 / 3.12 上运行测试，并编译、链接六个 ARM C 学习项目。自动测试通过不代表所有浏览器交互、各类操作系统性能或真实硬件已验收；执行人工验收时请按 [Windows 实机验收提示词](docs/windows-acceptance-prompt.md) 保留运行日志、波形与版本信息。

## 重要边界

zetsim 是用于嵌入式学习和功能验证的教学仿真器，不等同于完整电气级/逐周期精确模拟。GPIO 上下拉、输出阻抗和部分外设行为采用教学性近似；布线检查并非完整 ERC/DRC。真实电路上电前仍需单独核查供电、极性、限流、电压容限、电流能力与短路风险。
