# zetsim 手把手学习教程：跟着源码做 6 个实验

这份教程不是 API 目录，而是一条可以照着完成的实操路线：先运行现成固件，再打开对应的 C 项目阅读，随后只改一个小地方、重新编译、运行并观察结果。每节都包含“看哪个文件、先看哪几行、为什么这样写、动手改什么、什么现象算成功、失败时查哪里”。

建议每次只完成一节。不要一开始就通读整个仓库；每次围绕一个可观察的问题学习，效果会好得多。\n\n**零基础优先走库函数路线：** 先打开 `projects/hal_gpio_blink/main.c`，学习 `HAL_Init()`、`HAL_GPIO_Init()`、`HAL_GPIO_TogglePin()` 和 `HAL_Delay()`。它调用 ST 官方 STM32F1 HAL，而不是自己写的同名封装。原有 GPIO、跑马灯等案例仍保留为寄存器进阶课。详见 `projects/hal_gpio_blink/README.md`。

---

## 0. 先认识 zetsim：它在仿真什么？

zetsim 不是把 LED 动画画在网页上。它加载固件并模拟 STM32F103ZET6 的 CPU 指令、内存、部分外设寄存器和时间推进，再把 GPIO 等信号连接到虚拟器件上。

一次完整运行大致是：

1. C 源文件由 ARM 交叉编译器编译、链接成固件。
2. 固件中的机器码由 Cortex-M3 指令仿真内核执行。
3. 固件读写寄存器，改变 GPIO、定时器、ADC、USART 等外设状态。
4. 板级网络把引脚状态送到 LED、按键、探针或模拟电路。
5. 仪表盘显示 LED、串口文本、网络电压和波形。

理解这条链路，是排查问题的关键。例如 LED 不亮，不一定是 LED 画错了；也可能是 RCC 时钟没开、GPIO 模式没配置、固件没有加载，或者原理图网络没有接通。

### 学习时最常见的几个词

| 名词 | 可以先这样理解 | 本项目中的入口 |
|---|---|---|
| 固件 / HEX | MCU 实际执行的机器码，不是 C 源码 | firmware/、项目编译输出 |
| 寄存器 | 固件用特定内存地址控制外设的接口 | projects/*/stm32f103.h、zetsim/periph/ |
| RCC | 芯片的时钟与复位控制器；外设通常要先开时钟 | projects/*/main.c、zetsim/periph/rcc.py |
| GPIO | MCU 的输入输出引脚 | zetsim/periph/gpio.py、zetsim/board.py |
| 中断 / NVIC | 设备事件发生后，让 CPU 暂时转去执行处理函数 | projects/exti_button、zetsim/periph/exti.py |
| 定时器 / PWM | 硬件按周期产生计数或输出波形 | projects/pwm_adc_control、projects/pwm_rc_filter |
| ADC | 把模拟电压转换成数字读数 | projects/pwm_adc_control |
| 网表 | 把画布中的连线整理成实际电气连接关系 | zetsim/schematic.py |
| SPICE | 解电阻、电容、LED 等模拟电路的电压与电流 | zetsim/spice.py |

重要边界：本项目是以学习为目标的 MCU 仿真器，不等同于真实芯片的逐周期、晶体管级或完整电气仿真。通过仿真不能替代真实板卡的电压范围、发热、功耗、时序和安全核查。

---

## 1. 准备环境：先让项目能运行

以下命令在仓库根目录执行，也就是能看到 README.md、pyproject.toml、zetsim/ 和 projects/ 的目录。

### 1.1 确认 Python 环境

推荐使用 Python 3.11 或 3.12，并在虚拟环境中安装依赖。Windows PowerShell 示例：

    py -3.12 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"

如果你的组织要求使用已有虚拟环境，可以继续使用自己的环境，但要确保运行程序、安装依赖和执行 pytest 用的是同一个 Python。遇到“模块找不到”时，先运行 python -c "import sys; print(sys.executable)" 检查解释器路径。

### 1.2 准备 ARM C 编译器

教程中的 C 项目不是伪代码；需要 ARM bare-metal 编译器把 C 文件变成 STM32 可以执行的固件。可以先运行：

    python setup_env.py

脚本会尝试准备项目自己的工具链。如果电脑无法下载，可按团队环境的方式安装 Arm GNU Toolchain，并确认以下命令可用：

    arm-none-eabi-gcc --version
    arm-none-eabi-objcopy --version

如果暂时没有编译器，仍可以加载仓库中已生成的 HEX 固件学习仪表盘和外设行为；但要完成“改 C 源码再编译”的实战，就必须准备编译器。

**Windows 链接错误：** 如果编译日志显示 `ld.exe: cannot find -lgcc`，这是链接器找不到 GCC 运行库，并不一定是 main.c 有错误。更新到最新 DEV 后，构建器会查询 GCC 为 Cortex-M3/Thumb 选择的 `libgcc.a`，并把该库的完整路径传给链接器；若文件不存在，会在链接前报告运行库路径。可以在 PowerShell 执行：

    arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb -print-libgcc-file-name

将命令输出的路径代入下面的检查：

    Test-Path "上一步输出的完整路径"

结果应为 `True`。如果是 `False`，工具链安装可能不完整，请先运行 `python setup_env.py`；仍不通过时，重新安装完整的 Arm GNU Toolchain。若仓库路径含中文或特殊字符，可将项目另复制到纯英文路径（例如 `E:\\codebase\\zetsim`）后重试。不要手动从其他版本复制单个 `libgcc.a`，不同 GCC 版本/目标配置的运行库不应混用。

### 1.3 运行最小自动测试

    python -m pytest tests/ -q

测试通过说明当前环境中的自动回归检查通过，但它不代表每个浏览器交互、所有波形性能和真实硬件场景都已人工验收。后面仍要自己运行六个项目。

### 1.4 启动网页

    python -m zetsim serve

通常在浏览器打开：

    http://127.0.0.1:8000

若提示端口被占用，可以用另一个端口启动：

    python -m zetsim serve --port 8001

终端窗口不要关掉。它是服务进程的日志窗口；需要停服务时再回到该窗口按 Ctrl+C。

---

## 2. 先熟悉项目目录：遇到问题知道去哪找

不要一口气读完所有模块。先记住以下几个最有用的入口。

| 路径 | 学什么 | 什么时候打开 |
|---|---|---|
| projects/hal_gpio_blink/main.c | HAL 库函数版点灯，适合入门 | 第一次学库函数时 |\n| projects/gpio_blink/main.c | 第一个 C 程序、时钟、GPIO 和延时 | 第一次学习 |
| projects/*/stm32f103.h | 寄存器地址映射、volatile、结构体 | 看不懂 RCC 或 GPIO 定义时 |
| projects/*/startup.c | 向量表、启动入口、初始化 | 中断函数为什么能被找到时 |
| projects/*/link.ld | Flash/RAM 地址与链接布局 | 编译链接或内存布局问题 |
| zetsim/core.py | CPU、固件加载与指令执行的封装 | HEX 为什么可以运行时 |
| zetsim/bus.py | 内存映射与外设寄存器访问 | 固件访问寄存器时发生什么 |
| zetsim/board.py | 把 CPU、外设、引脚和器件装成一块板 | 一个引脚如何连到 LED |
| zetsim/engine.py | 推进仿真时间、外设事件和休眠 | 时间、WFI 或定时器问题 |
| zetsim/periph/gpio.py | GPIO 寄存器行为 | LED、引脚模式与电平问题 |
| zetsim/periph/exti.py、sysctrl.py | EXTI、NVIC、中断派发 | 按键中断问题 |
| zetsim/periph/usart.py | 串口寄存器和收发状态 | 串口回显问题 |
| zetsim/periph/tim.py、adc.py | PWM 定时器和 ADC | PWM/ADC 案例 |
| zetsim/schematic.py | 画布连接怎样变成电气网络 | 布线、原理图、探针问题 |
| zetsim/spice.py | R/C/LED 的模拟电路求解 | RC 电压、LED 电流、仿真速度问题 |
| zetsim/webapp.py、zetsim/static/index.html | 服务端接口和浏览器界面 | 只有 Web 行为异常时 |
| tests/ | 已经验证的行为约定 | 修改代码前找相似测试 |

### 一次只沿一条调用链阅读

例如学习 GPIO 闪灯时，依次看：

1. projects/gpio_blink/main.c：固件究竟写了什么寄存器。
2. projects/gpio_blink/stm32f103.h：这些寄存器名对应什么地址。
3. zetsim/bus.py 与 zetsim/core.py：固件对该地址的访问如何进入模型。
4. zetsim/periph/gpio.py：GPIO 模型如何保存输出状态。
5. zetsim/board.py 与 zetsim/devices.py：引脚状态如何影响 LED。
6. tests/：项目用什么输入与可观察结果验证这条链路。

初学阶段读完第 1、2 步并完成动手任务就够了；只有当结果不符合预期时，再沿链条向下追。

---

## 3. 每一课都按这个实验流程完成

1. **运行基线**：先不要修改代码，运行一次，记下默认现象。
2. **看源码**：按照该课给出的路径定位函数和关键寄存器。
3. **提出预测**：改动前写下“我认为修改后会发生什么”，尤其是周期、占空比、电压或中断次数。
4. **只改一个因素**：例如只改 BLINK_MS，不要同时改寄存器配置和电路接线。
5. **保存并编译**：浏览器项目工作台中保存，再编译运行；或使用命令行构建。
6. **观察与记录**：比较 LED、串口、探针波形或日志，而不只看“编译成功”。
7. **恢复或保存成果**：记录改变了哪一行、现象是否符合预测、为什么。继续下一课前确认工程状态清楚。

浏览器工作台里，Ctrl+S 保存，Ctrl+Enter 保存并编译运行。注意：浏览器中保存到本地项目目录不等于 Git 提交，也不会自动推送到 GitHub。

---

# 实战 01：GPIO 闪灯——从 C 代码到 LED

## 学习目标

理解一个最简单的 MCU 程序怎样打开外设时钟、配置引脚、改变输出状态，并让虚拟 LED 产生真实的状态变化。

## 第一步：打开项目

在浏览器工具栏打开「项目」，选择 gpio_blink。也可以直接打开：

    projects/gpio_blink/main.c
    projects/gpio_blink/stm32f103.h
    projects/gpio_blink/README.md

先只读 main.c，不急着改代码。建议按下面顺序阅读。

### 关键点 A：先开 RCC 时钟

    RCC->APB2ENR |= (1u << 2);

GPIOA 连接在 APB2 时钟域。这里将 APB2ENR 的 bit 2 置 1。为什么是先开时钟？因为外设时钟没有使能时，访问该外设的寄存器可能无法产生预期行为。把它想成“先给设备通电，再配置设备”。

### 关键点 B：配置 PA5 模式

    GPIOA->CRL = (GPIOA->CRL & ~(0xFu << 20)) | (0x2u << 20);

CRL 配置 PA0–PA7，每个引脚占 4 位。PA5 对应从 bit 20 开始的 4 位。表达式先清掉这 4 位，再写入 0x2，设置成通用推挽输出、2MHz 速度。

为什么不能直接把整份 CRL 随意写成一个值？因为那会同时改到 PA0–PA4、PA6、PA7 等其他引脚。先清目标位再设置目标位是更安全的寄存器操作习惯。

### 关键点 C：翻转输出

    GPIOA->ODR ^= LED_PIN;

LED_PIN 是第 5 位掩码。异或操作会把这一位从 0 变 1，或从 1 变 0；其他位保持不变。因此循环每执行一次，LED 就改变一次状态。

### 关键点 D：SysTick 延时

    #define BLINK_MS 250u

延时函数把 LOAD 写成 8000 × 毫秒数 − 1，再启动 SysTick，等待 COUNTFLAG 置位。示例按默认 8MHz HSI 解释：每毫秒约有 8000 个时钟。它是教学延时模型，不要把该写法不加检查地用于任意系统时钟。

## 第二步：完成第一个实验

1. 先按默认值运行，观察 LED 与 PA5 探针。
2. 将 BLINK_MS 从 250 改成 100。
3. 保存并编译运行。
4. 观察 LED 翻转间隔是否变短。
5. 再把它改成 500，观察更慢的变化。

预期：100ms 时每约 100ms 发生一次状态翻转；500ms 时每约 500ms 翻转一次。每次翻转不等于完整的亮灭周期；亮再灭的完整周期通常包含两次翻转。

## 第三步：自测问题

- RCC 的 bit 2 为什么必须先置位？
- 为什么 PA5 的配置位从 bit 20 开始？
- XOR 翻转与直接写 ODR=0 / ODR=1 有什么区别？
- 如果 LED 状态不变，除了代码，还应检查哪些原理图连接？

命令行构建：

    python -m zetsim build projects/gpio_blink

常见问题：编译失败先看日志中的源文件名和行号；编译成功但 LED 不亮，检查工程是不是已成功加载运行、PA5 是否连到了 LED 回路、串联电阻和 GND 是否存在。

---

# 实战 02：8 路跑马灯——位运算和 GPIO 组合输出

## 学习目标

把单个引脚的控制扩展到 8 个引脚，理解位掩码、循环、共享寄存器以及为什么 LED 回路需要独立限流电阻。

## 先读哪一段？

打开 projects/led_marquee/main.c，重点看 led_init()、LED(i) 和 main() 中的超级循环。

    #define LED(i) (1u << (i))
    #define STEP_MS 100

当 i=0 时，掩码是 00000001；i=1 时是 00000010；i=2 时是 00000100。每次只把一个输出位置为 1，其余位置为 0。

初始化代码把 GPIOA 的 CRL 配成 0x22222222，让 PA0–PA7 都成为通用推挽输出。随后主循环把掩码写入 ODR、等待 STEP_MS，再移动到下一位，走到 7 后回到 0。

## 实验步骤

1. 在画布中载入“8-LED 跑马灯”推荐电路。
2. 检查 PA0–PA7 的每条支路都经过自己的 330Ω 电阻，再进入对应 LED。
3. 打开 projects/led_marquee/main.c。
4. 将 STEP_MS 从 100 改为 60，保存并编译运行。
5. 将 STEP_MS 再改成 200，观察两种速度。
6. 进阶：尝试让跑马灯从 PA7 向 PA0 倒序移动。先写下你准备怎样改变 i，再动手。
7. 运行布线检查，留意缺失限流电阻、无效端子和重复连线报告。

预期：灯按顺序移动，速度随 STEP_MS 改变。如果只有一盏灯亮、所有灯一起亮或顺序错乱，检查 PA0–PA7 的接线顺序和 ODR 写入值。

## 思考题

- 为什么 LED(i) 使用 1u，而不是普通的有符号整数 1？
- 写 ODR=LED(i) 与逐位异或的效果有何不同？
- 为什么每个 LED 应有自己的限流电阻？
- 改变 STEP_MS 只影响速度，为什么不需要改 CRL？

---

# 实战 03：按键中断——理解 EXTI、NVIC 和 WFI

## 学习目标

理解轮询和中断的差别，追踪一次按键从输入引脚到中断处理函数的完整链路。

## 先读源码

打开：

    projects/exti_button/main.c
    projects/exti_button/startup.c
    projects/exti_button/README.md

main.c 中关键配置包括：

- RCC：打开 AFIO 和 GPIOA 时钟。
- GPIOA：把 PA0 配成输入，把 PA5 配成输出。
- AFIO_EXTICR1：选择 EXTI0 使用 Port A。
- EXTI_IMR：允许 EXTI0 请求通过。
- EXTI_RTSR：选择上升沿触发。
- NVIC_ISER0 的 bit 6：允许 EXTI0 IRQ。
- EXTI0_IRQHandler：翻转 LED，并向 EXTI_PR 对应位写 1 清除 pending 标志。

中断链可以写成：

    SW1 → PA0 → EXTI0 边沿检测 → NVIC IRQ6
        → EXTI0_IRQHandler → 改变 PA5 → LED 改变

这里的 GPIO 输入配置和 EXTI 中断配置是两个不同层次；仅把 PA0 设成输入，并不会自动打开中断。

## 动手实验

1. 编译并运行 exti_button。
2. 在画布按下再松开 SW1，观察 LED 是否翻转。
3. 完整按键五次，记录实际触发次数。
4. 只做一次临时实验：注释 NVIC_ISER0 的使能语句，重新编译运行，观察中断是否还会进入。完成后恢复原代码。
5. 再检查 EXTI_PR 清除语句：先解释为什么需要清 pending，再决定是否做对照实验；实验后务必恢复。
6. 打开 startup.c，找到 EXTI0_IRQHandler 如何关联到向量表。不要只看函数名，要看启动表里是否确实登记。

预期：每次有效按下都触发一次翻转。若没有触发，按 RCC、GPIO 输入、AFIO 路由、触发边沿、EXTI_IMR、NVIC、向量表、pending 清除的顺序检查。

## 进一步理解

主循环末尾的 WFI 表示 CPU 在等待中断时休眠。定时器/外设事件仍应由仿真引擎推进；出现“按键第一次有效、后续无反应”时，需要判断是中断标志没有清除，还是运行状态/仿真调度有问题。

---

# 实战 04：USART1 回显——寄存器状态位与字符收发

## 学习目标

跟踪浏览器中输入的字符怎样进入 MCU，再由固件写回串口终端。理解 TXE 与 RXNE 是两个不同的状态位。

## 先读源码

打开 projects/uart_echo/main.c。找到以下内容：

- RCC：开启 GPIOA 与 USART1 时钟。
- GPIOA_CRH：PA9 配为 USART1_TX 复用推挽输出，PA10 配成 RX 输入。
- USART1_BRR：在默认 HSI 8MHz 教学条件下设置近似 115200 baud。
- USART1_CR1：打开 USART、发送器与接收器。
- TXE（SR bit 7）：发送数据寄存器可以写入新数据。
- RXNE（SR bit 5）：收到一个字节，数据寄存器可读。
- USART1_DR：读接收到的字节、或写入要发送的字节。

程序是轮询实现：主循环不断看 RXNE；收到数据后读取 DR，再等 TXE 可以发送时把字符写回。它不是靠中断来接收。

## 动手实验

1. 选择 uart_echo 工程并编译运行。
2. 等待终端显示固件启动问候语。
3. 在 USART1 终端逐个输入 hello，再输入一段较长文本。
4. 改动 main.c 里的启动问候语，保存、编译、运行，验证新问候语出现。
5. 试着回答：如果没有 RXNE 就直接读取 DR，代码可能会有什么问题？如果不等 TXE 就连续写，可能会丢掉什么？

预期：输入字符由固件逐字节回显，启动问候语随源码修改变化。若终端空白，检查工程是否正在运行、加载的是哪个固件、USART1 是否正确启动以及终端是否选中 USART1。

---

# 实战 05：电位器 ADC 控制 PWM——从模拟输入到定时器输出

## 学习目标

观察一个闭环式信号链：电位器给出电压，ADC 将电压转换为数字值，固件把采样值映射成定时器比较值，PWM 占空比随之改变。

## 先读源码

打开 projects/pwm_adc_control/main.c。逐个定位：

1. ADC1_SQR3：选择规则序列通道 1，对应 PA1。
2. ADC1_CR2：启动 ADC，并设置连续转换。
3. ADC1_SR 的 EOC 位：本次转换完成。
4. ADC1_DR：读出 12 位采样值，范围约为 0–4095。
5. TIM2_PSC=7、TIM2_ARR=99：在相关定时器时钟为 8MHz 的前提下，目标 PWM 频率为 10kHz。
6. TIM2_CCR1：比较值决定 PWM 占空比。
7. 计算式把 ADC 值映射到约 5%–95% 的占空比范围，避免长期贴在 0% 或 100%。

注意：ADC 的数值和 PWM 占空比是两回事。ADC 读的是输入电压；CCR 是定时器的比较值。

## 动手实验

1. 编译运行 pwm_adc_control。
2. 把探针接到 PA0，观察 PWM；将另一个探针（或仪表）放到 PA1 所在网络。
3. 缓慢拖动电位器，观察 PA1 电压变化。
4. 同时观察 PA0 的占空比，而不只看是否有方波。
5. 把映射范围从 5..95 改成 10..80，保存并编译，比较低、中、高电位器位置的响应。
6. 恢复或记录修改，确保知道最后运行的是哪一版固件。

预期：PA0 频率大致保持在 10kHz，电位器改变时占空比随之改变。若 PA1 电压变化、但 PWM 占空比不变化，按 ADC 通道、EOC、DR 读取、映射计算、CCR 写入、定时器输出使能的顺序排查。

## 思考题

- ADC 的满量程为什么是 4095，而不是 4096？
- 改变 CCR 为什么主要改变占空比，而不直接改变由 PSC/ARR 决定的频率？
- 输入电压为零时，为什么代码仍可能输出大于零的最小占空比？

---

# 实战 06：PWM + RC 低通滤波——同时看数字波形和模拟电压

## 学习目标

理解数字输出和模拟节点不是同一种信号，学会使用时间常数预测电路响应，并对照 SPICE 探针结果。

## 先看项目和电路

打开：

    projects/pwm_rc_filter/main.c
    projects/pwm_rc_filter/README.md
    zetsim/schematic.py
    zetsim/spice.py

建议在画布中搭建：

    PA0 / PWM → 1kΩ 电阻 → RC 节点
    RC 节点 → 100nF 电容 → GND
    探针 1 → PA0 原始 PWM
    探针 2 → RC 节点

电阻和电容的串接位置很重要。探针要接到真正的 RC 节点，不要只放在器件旁边。

## 先预测，再运行

时间常数：

    τ = R × C = 1000Ω × 100nF = 100µs

10kHz PWM 的周期为 100µs。30% 占空比、3.3V 高电平的理想平均值约为：

    Vavg = 3.3V × 0.30 = 0.99V

先写下预测：RC 节点与原始 PWM 相比，哪个更平滑？把电容从 100nF 改成 220nF 后，纹波和响应速度会怎样变化？

## 动手实验

1. 编译运行 pwm_rc_filter。
2. 先只观察 PA0：确认它大致为 10kHz、30% 占空比的方波。
3. 接入 1kΩ + 100nF RC 网络，并在 RC 节点放置探针。
4. 对比两个探针：原始 PWM 是方波，RC 节点应呈现较平滑的充放电波形。
5. 将电容改为 220nF，保持其他条件不变，记录纹波范围与达到稳定状态所需时间。
6. 恢复 100nF，再把 CCR1 从 30 改成 60，预测平均电压后观察。
7. 再用带 LED 的电路做对照：它是非线性器件参与的电路，数值求解路径可能与纯 RC 不同。

## 怎样判断结果？

- 30% 占空比的理想平均电压约为 0.99V；实际探针读数会受采样窗口、初始状态、步长和波形纹波影响。
- 电容增大通常让节点变化更慢，纹波趋于减小。
- 如果 PA0 正常而 RC 节点始终为 0，先检查接线、公共 GND、探针节点和仿真时间是否足够。
- 如果波形正确但仿真时间远慢于墙钟，应记录性能数据并提交报告；不要为了让波形“看起来快”就随意加大积分步长，因为这可能改变数值结果。

本案例同时是学习 zetsim 内部实现的入口：zetsim/schematic.py 把画布连接转成网络；zetsim/spice.py 对电阻、电容、源和二极管求解。先理解实验现象，再读算法，效率会更高。

---

## 4. 看懂 C 工程中的四个文件

六个可编译工程通常都包含 main.c、startup.c、stm32f103.h 和 link.ld。这里需要特别说明：`stm32f103.h` 现在只是一个很薄的兼容包装，不再手写寄存器结构体。实际设备定义来自 ST 官方 CMSIS 的 `third_party/cmsis-device-f1/Include/stm32f103xe.h`，核心 Cortex-M3 定义来自 ARM CMSIS。STM32F103ZET6 使用 `STM32F103xE` 型号选择宏；官方 CMSIS 设备头文件名是 `stm32f103xe.h`，而不是按完整订货号命名的 `stm32f103zet6.h`。

要追溯这些定义，可打开 [third_party/README.md](../third_party/README.md)，其中记录了上游仓库、固定版本提交号和许可证。不要直接编辑厂商头文件来“适配”示例；示例项目保留 `stm32f103.h` 作为兼容入口，构建器会自动添加官方 CMSIS include 路径。

六个可编译工程通常都包含 main.c、startup.c、stm32f103.h 和 link.ld。可以把它们理解成四个不同的问题。

| 文件 | 它回答的问题 | 学习时怎么读 |
|---|---|---|
| main.c | 程序要做什么？ | 从 main() 开始，跟着初始化函数和主循环读 |
| stm32f103.h | 寄存器名字与地址是什么？ | 找到源代码中用到的结构体、基地址、位偏移 |
| startup.c | 复位后 CPU 从哪里开始？中断函数怎样被找到？ | 看向量表、Reset_Handler、数据段初始化和 IRQ 项 |
| link.ld | 机器码放进 Flash/RAM 的哪里？ | 看 FLASH、RAM 区域以及 .text、.data、.bss 段的布局 |

学习顺序始终先 main.c。等看到它引用了寄存器、启动函数或向量表，再跳到对应文件。不要先逐行读 link.ld，也不要把自动生成的寄存器地图当作普通业务代码随意修改。

## 5. 编译、加载、运行：命令行和浏览器各自负责什么？

### 浏览器工作台

1. 在「项目」里选择工程。
2. 编辑 main.c。
3. 看未保存状态，按 Ctrl+S 保存。
4. 按 Ctrl+Enter 保存并编译运行。
5. 查看编译日志和运行表现。
6. 修改后再运行前，确认没有未保存内容，并确认当前选择的工程名。

如果切换项目时有未保存更改，先明确决定保存还是放弃，不要把一个工程的缓冲区误写入另一个工程。

### 命令行

单独构建一个工程：

    python -m zetsim build projects/gpio_blink

同理，可替换为 projects/led_marquee、projects/exti_button、projects/uart_echo、projects/pwm_adc_control 或 projects/pwm_rc_filter。

运行已有 HEX 固件：

    python -m zetsim run firmware/blink.hex --time 2s
    python -m zetsim run firmware/hello_echo.hex --time 50ms --uart 1

查看 GPIO 事件：

    python -m zetsim run firmware/blink.hex --time 2s --trace-gpio

结束时输出 CPU 寄存器快照：

    python -m zetsim run firmware/blink.hex --time 500ms --dump

命令行适合重复、可脚本化的检查；浏览器适合手动交互、搭电路和看波形。两者应建立在同一套仿真核心上。

---

## 6. 当结果不符合预期时，按证据排查

不要一下子改很多地方，也不要一出现异常就判断整个模拟器有问题。先确认故障属于哪一层。

| 现象 | 第一轮检查 | 第二轮检查 |
|---|---|---|
| 构建命令找不到 | Python 虚拟环境是否激活；是否在仓库根目录 | 运行 python -m zetsim --help，确认安装路径 |
| ARM 编译器不存在 | arm-none-eabi-gcc --version | 按 setup_env.py 输出安装或修复工具链 |
| 链接时报 cannot find -lgcc | 用 -print-libgcc-file-name 查询库路径，并用 PowerShell Test-Path 检查文件存在 | 运行最新版 setup_env.py 校验/重装工具链；检查项目路径是否含中文或特殊字符 |
| 编译成功但 LED 不动 | 固件是否加载运行；LED 回路与 GND 是否接通 | RCC、GPIO 模式、ODR/BSRR/BRR 写入 |
| 跑马灯顺序异常 | PA0–PA7 连接顺序和各路电阻 | ODR 掩码、i 的边界条件 |
| 按键触发不了 | 输入引脚与按键连线 | AFIO、EXTI、NVIC、向量表、pending 清除 |
| 串口没有回显 | 是否加载正确固件、终端是否是 USART1 | GPIO 复用、BRR、UE/TE/RE、RXNE/TXE |
| 电位器变化但 PWM 不变 | PA1 是否真正接到 ADC 输入网络 | ADC 通道、EOC、DR、CCR 与定时器输出 |
| RC 探针一直为 0 | 探针是否在 RC 节点；有没有公共 GND | 固件是否输出 PWM、网络是否进入 SPICE、观测窗口是否足够 |
| 浏览器报 4xx/5xx | 记录请求路径和响应信息 | 查终端日志、检查是否存在未保存的原理图同步状态 |
| 页面显示异常但 CLI 正常 | 用相同固件做无头对照 | 区分引擎、原理图同步、浏览器渲染问题 |
| 仿真时间明显落后墙钟 | 记录墙钟秒数和 t_ms 的增量 | 分别测试无电容、纯 RC、RC+LED；不要混合比较不同电路 |

排查时留存四种证据：当前分支和提交号、准确复现步骤、终端/浏览器 Console 与网络错误、预期和实测数值。只写“还是不行”很难定位问题。

---

## 7. 学完六课后，尝试完成三个挑战

### 挑战 A：从零复刻闪灯

不复制现成 main.c，自己写出 RCC 时钟开启、PA5 输出配置、输出翻转和延时。完成后把自己的代码与 gpio_blink 对照，解释每个寄存器操作。

### 挑战 B：给回显程序增加前缀

修改 uart_echo 的回显逻辑，让收到的字符前先输出固定前缀。先列出预期输出，再编译、输入至少三种字符序列，检查顺序是否正确。

### 挑战 C：预测 RC 再验证

用不同 R、C 参数计算时间常数，然后搭电路观察启动与稳定波形。记录参数、预测、平均值、纹波、仿真时间和墙钟时间。不要只记录一张截图。

每个挑战完成后保留一份简短实验笔记：

- 我想验证什么：
- 修改了哪个文件、哪几行：
- 运行前的预测：
- 实际结果（数值/截图/日志）：
- 预测和实测为什么一致或不同：
- 我下一步会怎样验证：

## 8. 自动测试能证明什么，不能证明什么？

运行：

    python -m pytest tests/ -q

可以验证当前代码版本中被测试覆盖的行为，包括指令执行、外设、引脚网络、原理图同步和部分 RC 响应。但自动测试不可能覆盖每个操作系统版本、每种浏览器、每次人工拖线和每一个真实工程。

涉及学习工具工作台时，还要人工验证保存、切换项目、编译错误显示以及实际运行；涉及混合仿真时，还要同时记录数值是否正确、仿真时间推进速度和探针历史是否填充。

布线检查只是基础教学规则，不是完整 ERC/DRC。真实板卡上电前，需要另行审核供电、极性、限流、电流能力、引脚电压容限和短路风险。

## 9. 建议的学习顺序与完成标准

| 阶段 | 需要能做到的事 | 证明方式 |
|---|---|---|
| 入门 | 修改闪灯时间并解释 RCC/GPIO/SysTick | 改动前后运行记录 |
| 数字输出 | 写出跑马灯位掩码与循环 | 八路 LED 的观察结果 |
| 中断 | 解释从 PA0 到 EXTI0_IRQHandler 的链路 | 五次按键的触发记录 |
| 串口 | 解释 RXNE/TXE 并修改问候语 | 终端输入/输出记录 |
| 定时器与 ADC | 解释 ADC 读数如何影响 TIM2_CCR1 | PA1 输入与 PA0 占空比对照 |
| 模拟电路 | 计算 τ 与平均电压，并解释纹波 | 预测、探针截图和实测数据 |
| 工程阅读 | 能根据现象找到可能责任模块 | 文件路径和调用链说明 |
| 独立排障 | 能提供提交号、复现步骤和有用日志 | 一份结构化问题报告 |

完成课程的目标不是背下所有寄存器，而是建立可靠的调试习惯：先提出可检验的预测，沿着源码的信号链定位，再用可观测数据判断问题。
