# zetsim — STM32F103ZET6 个人仿真器 · 总体架构

> 目标：复现"Keil 编译 → 加载 .hex → 芯片在仿真器里真跑代码、外设联动、虚拟器件交互"的 Proteus 式体验。
> 只支持一颗芯片：STM32F103ZET6（Cortex-M3 @72MHz, 512KB Flash, 64KB SRAM, 144 脚）。
> 定位：个人学习项目，精度目标 = 功能级精确 + 时序近似（误差 ±10~20%），不做电气级（M7 通过内置 mini-SPICE 补局部电气）。

## 实现落地说明（与初版设计的差异）

- **M7 混合仿真用内置 mini-SPICE**（`zetsim/spice.py`：MNA + 后向欧拉 + 二极管 Newton 迭代），
  而非外接 ngspice —— 零外部 DLL 依赖、Windows 下开箱即用，RC/LED 教学电路精度足够（<2%）。
- **SVD 成功落地**：`firmware/STM32F103.svd`（modm-io 镜像，Apache-2.0）经 `tools/svd_gen.py`
  生成 `zetsim/regmap.py` + `docs/registers.md`，并有测试交叉验证 30 个模型基址与 SVD 一致。
- **测试固件来自自研迷你 Thumb-2 汇编器**（`zetsim/asm.py`）：主机无 arm 交叉工具链时
  仍可完全自包含地生成/验证固件；用户自己的 Keil/GCC 固件照常加载。
- **异常引擎机制定稿**（经 `tools/probe_unicorn.py` 微测试）：
  Unicorn 直接暴露 MSP/PSP/CONTROL/PRIMASK/BASEPRI；MMIO 用"映射+读前注入"钩子；
  异常返回靠 PC 魔数 + UcError 捕获；WFI/SVC/BKPT 用代码钩子拦截。

---

## 0. 设计原则（六条，全项目不变）

1. **引擎无头（headless）**：仿真核心不依赖任何 UI。CLI、网页仪表盘、示波器都只是事件订阅者。前端可以随时换，引擎一行不改。
2. **一切时间来自统一时钟源**：外设模型永远只问 `TimeModel.now_ns()` 和 `ClockTree.pclk_hz()`，自己不持有时钟。时间模型可整体替换（常量 → 加权周期表），外设无感知。
3. **总线中心**：CPU 眼里只有内存。SystemBus 负责地址解码、bit-band 翻译、MMIO 分发到外设。外设 = 挂在总线上的纯 Python 对象，可独立单元测试。
4. **寄存器表自动生成，行为手写**：地址/位域来自 SVD 解析（零手抄错误）；行为照 RM0008 手写，Renode 开源实现作对照答案。
5. **精度由固件测试合同保证**：每个外设绑定一组真实参考固件（标准外设库例程编译的 .hex），断言其可观测输出（串口字节、引脚波形、ADC 值）。精度是看板，不是感觉。
6. **数字语义先行，电气语义是升级不是重构**：引脚网络（Net）M2 起用数字电平（0/1/高阻 + 可选模拟电压值），M7 起同一接口桥接 ngspice 节点。

---

## 1. 分层总览

```
┌────────────────────────────────────────────────────────────┐
│  前端层  cli (M1)  →  web 仪表盘 (M4+)  →  桌面 GUI (可选)    │
│          只订阅 EventBus，不碰引擎内部                        │
├────────────────────────────────────────────────────────────┤
│  引擎层  SimLoop 仿真循环 · EventBus 事件总线 · Recorder 录制  │
│          ngspice_bridge (M7 混合仿真)                        │
├────────────────────────────────────────────────────────────┤
│  板级层  Board: F103ZET6 引脚映射(144脚/AF表) · Net 导线网络   │
│          Devices: LED / 按键 / 电位器 / 示波器 / OLED ...     │
├────────────────────────────────────────────────────────────┤
│  外设层  RCC · SysTick · NVIC · GPIO · EXTI · USART · TIM    │
│          ADC · DAC · DMA · SPI · I2C · WDG · RTC · (CAN/USB) │
├────────────────────────────────────────────────────────────┤
│  基础层  SystemBus(地址解码/bit-band/MMIO分发)                │
│          ClockTree(实时解析RCC) · TimeModel(可替换)           │
├────────────────────────────────────────────────────────────┤
│  核心层  Cpu (Unicorn 封装) · Loader(.hex/.elf) · MemoryMap   │
│          ExceptionEngine (NVIC 异常入口/出口，自实现)          │
└────────────────────────────────────────────────────────────┘
```

依赖方向严格自上而下；外设层与板级层通过 Net/引脚解耦（外设不知道 LED 的存在）。

---

## 2. 核心层（core/）

### 2.1 Cpu — Unicorn 封装

```python
class CortexM3Core:
    """UC_ARCH_ARM + UC_MODE_THREE|UC_MODE_MCLASS（Cortex-M3 专属模式）"""
    def __init__(self, bus: SystemBus, time: TimeModel): ...
    def load_firmware(self, path) -> FirmwareInfo    # .hex/.elf → 烧入 Flash，取向量表设 SP/PC
    def run_slice(self, max_cycles: int) -> int      # 执行一段指令，返回实际耗时 ns
    def request_exception(self, exc_no: int)         # 异常入口：压栈 + EXC_RETURN + 跳向量
    # Unicorn 钩子：MEM_READ/WRITE → bus 分发；CODE → time.instruction_cost() 计时
```

- **内存映射**：Flash @ `0x0800_0000`(512K, 只读)、SRAM @ `0x2000_0000`(64K)，
  另在 `0x0000_0000` 做 Flash 只读别名（Boot0=0 时向量表重映射，固件启动读 0x0 向量表必须能通）。
- **MMIO 策略**（M1 定稿，两个候选）：
  - 方案 a（首选）：外设地址区**不映射**进 Unicorn，用 `UC_HOOK_MEM_INVALID` 拦截未映射访问 → 临时映射页 + 写入模型返回值 → 放行重试。读副作用（如读 USART DR 清 RXNE）天然正确。
  - 方案 b（备选）：外设区映射为"影子内存" + 写钩子同步模型，读前批量回写影子。速度略优，读副作用要特判。

### 2.2 ExceptionEngine — 全项目最难的 10%

Unicorn 只仿真指令，**不含 NVIC/异常机制**，需按 ARMv7-M 手动实现：

- `request_exception(n)`：NVIC 判优先级/抢占 → 在时间片边界压栈
  `{R0-R3, R12, LR, PC, xPSR}`（MSP/PSP 按 EXC_RETURN 规则）→ `LR = 0xFFFFFFF9/0xFFFFFFFD` → `PC = 向量表[n]`；
- 捕获 `BX LR` 且 LR 为 EXC_RETURN 魔数 → 出栈返回、恢复 ISR 活跃状态；
- SysTick / 外设 IRQ / SVC / PendSV 全部走这一条通道；
- **验收标准：FreeRTOS 跑起来（M6）**——PendSV 任务切换对异常引擎的正确性是"期末考试"。

### 2.3 Loader

- `.hex`：intelhex 库解析；`.elf`：pyelftools 按 segment 烧入；
- 统一从 Flash 起始的向量表取初始 SP/PC（PC 最低位置 1 表示 Thumb）。

---

## 3. 基础层

### 3.1 SystemBus（bus.py）

```python
class SystemBus:
    def map(self, start: int, size: int, backend): ...
    def read(self, addr: int, size: int) -> int     # 未映射 → HardFault
    def write(self, addr: int, size: int, val): ...
```

- 地址解码：先查区间表 → RAM/Flash 直通，外设区转发 `peripheral.read/write(offset, size)`；
- **bit-band 翻译层（必须尽早做，M1~M2）**：`0x2200_0000`/`0x4200_0000` 别名区 → 目标字地址 + 位号，纯地址数学，做一次全外设受益（HAL 和 RTOS 大量使用 bit-band，不做则常见固件直接跑飞）。

### 3.2 ClockTree（clock/clocktree.py）

实时解析 RCC 的 CR/CFGR 寄存器：HSI/HSE/PLL → SYSCLK → AHB/APB1/APB2 分频 → 每个外设的 `pclk_hz()`。
**固件把 PLL 拉到 72MHz，定时器/串口波特率随之真实变化** —— 这一个设计决定保证了 PWM 频率与波特率的功能级精确。

### 3.3 TimeModel（clock/timemodel.py，可替换组件）

```python
class TimeModel(Protocol):
    def now_ns(self) -> int
    def instruction_cost(self, instr_info) -> int   # 返回周期数
```

- **A 常量模型**（M1 起）：1 指令 ≈ k 周期，校准到量级正确；
- **B 加权周期表**（M4 前后升级）：Thumb-2 各类指令真实周期数 + Flash 等待周期（72MHz 时 2 wait-state）近似，目标误差 ±10~20%；
- 外设只消费时间，升级时外设零改动。

---

## 4. 外设层（peripherals/）

统一基类：

```python
class Peripheral:
    name: str; base_addr: int; size: int
    def reset(self): ...
    def read(self, off: int, size: int) -> int
    def write(self, off: int, size: int, value: int) -> None
    def step_to(self, now_ns: int) -> None          # 推进自身状态到时刻 now_ns
    def next_event_ns(self) -> int | None           # 告诉调度器下一次关键事件（如定时器溢出）
    irqs: dict[int, IRQLine]                        # 中断号 → NVIC 请求线
```

实现顺序（依赖排序）：

```
RCC → SysTick → GPIO → EXTI/NVIC → USART → TIM通用 → ADC → DMA
→ TIM高级 → SPI/I2C → DAC/WDG → RTC → bxCAN → SDIO/FSMC → USB(可选末关)
```

**写法纪律**（每个外设三件套）：
1. `regs` 寄存器表：`tools/svd_gen.py` 从官方 SVD 生成（地址/位域/枚举），禁止手抄；
2. 行为：照 RM0008 对应章节手写 `read/write/step_to`，拿 Renode 同名模型源码对照边界行为（TXE 何时置位、读 DR 的副作用、计数器重装载语义）；
3. 测试：绑定参考固件 + 断言（见 §8），过了才算完成。

---

## 5. 板级层（board/ + devices/）

```python
class Net:                       # 一根导线
    level: int                   # 0 / 1 / Z(高阻)     —— M2~M6 数字语义
    analog_v: float | None       # 可选模拟电压(电位器→ADC 用)
    # M7 起：增加电气语义（节点电压/驱动强度），桥接 ngspice

class Device:                    # LED/按键/电位器/示波器/OLED...
    pins: dict[str, Net]
    def step_to(self, now_ns): ...
```

- `Board` 持有 F103ZET6 的 144 脚 → GPIO 端口/引脚/AF 功能映射表（数据手册公开表格，一次性录入）；
- 器件只跟 Net 打交道，不知道 MCU 存在 → M7 换成电气 Net 时器件层几乎不动；
- 示波器/逻辑分析仪本质是"订阅引脚事件 + 时间戳采样"的记录设备。

---

## 6. 引擎层（engine/）—— 仿真循环，心脏

**时间片锁步（time-slice lockstep）+ 下一事件自适应**：

```python
while now < target:
    slice_ns = min(BASE_SLICE_NS, 最近的 next_event_ns - now)   # 自适应收缩
    cpu.run_slice(slice_ns)            # ① CPU 跑一段指令，TimeModel 累计时间
    for p in peripherals: p.step_to(now)   # ② 推进外设(TIM计数/UART移位/SysTick)
    deliver_due_interrupts()           # ③ 到期中断经异常引擎注入（片边界，延迟≤片长）
    drain_events()                     # ④ 排水：串口字节/引脚翻转/ADC采样 → EventBus
    for d in devices: d.step_to(now)   # ⑤ 器件推进（LED 已在 ④ 收到电平）
```

- BASE_SLICE 默认 ~100µs 量级，可调；有定时器即将到期时自动收缩到事件点 → 中断延迟做到微秒级，无需周期精确；
- **EventBus**：主题式发布订阅（`usart1.tx` / `gpio.pa5.level` / `adc1.sample` / `sim.reset`）。CLI 打印、示波器、GUI 全是订阅者；
- **Recorder**：输入脚本化（按键何时按下）+ 事件录制 → 同固件同输入必然同结果，回归测试与"倒放调试"的地基；
- **ngspice_bridge（M7）**：固定步长锁步——MCU 片末把引脚状态作为激励喂给 ngspice 节点，ngspice 算完把节点电压回灌输入引脚，片长即同步粒度。

---

## 7. 前端层

- **M1 CLI**：`zetsim run blink.hex --uart1` —— 跑固件、串口打到终端、Ctrl+C dump 寄存器/外设状态快照；
- **M4+ 仪表盘**：FastAPI/WebSocket + 浏览器画布（示波器波形、点按按键、拖电位器）或 PySide6，**M4 时再定**，架构上引擎无感知；
- 前端永远通过 EventBus + 控制命令（暂停/单步/注入输入）与引擎交互。

---

## 8. 测试体系 —— 精度合同（tests/ + firmware/）

```
firmware/               # 参考固件资产（Keil 编译产物）
  blink_stdlib.hex      # 标准外设库例程：SysTick+GPIO 闪烁
  uart_echo.hex         # 串口回环
  pwm_out.hex           # TIM3 PWM
  adc_dma.hex           # ADC+DMA 循环采样
  freertos_blink.hex    # RTOS 双任务
tests/
  harness.py            # run(hex, until_ms, inputs) → RunReport(事件流)
  test_usart.py         # 断言：喂入 RX 字节 → TX 捕获到回显字节
  test_tim.py           # 断言：捕获引脚翻转 → PWM 频率 == 72MHz/psc/arr
  ...
```

- 每个外设的"完成"定义 = 其固件测试通过；
- `docs/accuracy.md` 维护精度看板：外设 × 测试 × 状态，一眼看清仿真器成色；
- 全部测试进 CI（本地 pytest），任何模型改动必须保持绿灯。

---

## 9. 目录结构

```
zetsim/
├─ ARCHITECTURE.md        # 本文档
├─ pyproject.toml
├─ zetsim/
│  ├─ core/               # cpu.py · exceptions.py · loader.py · memory.py
│  ├─ bus.py              # SystemBus + bit-band
│  ├─ clock/              # timemodel.py · clocktree.py
│  ├─ peripherals/        # base.py · rcc.py · sys_tick.py · gpio.py · exti.py ·
│  │                      # nvic.py · usart.py · tim.py · adc.py · dma.py · spi.py · i2c.py ...
│  ├─ regs/               # SVD 生成的寄存器表（自动生成，勿手改）
│  ├─ devices/            # led.py · button.py · potentiometer.py · oscilloscope.py · oled.py
│  ├─ board/              # f103zet6.py(引脚映射) · net.py
│  ├─ engine/             # loop.py · events.py · recorder.py · ngspice_bridge.py(M7)
│  └─ cli.py
├─ tools/svd_gen.py       # SVD → regs/ 代码生成
├─ tests/                 # harness + 每外设断言
└─ firmware/              # 参考固件 .hex（测试资产，Keil 编译）
```

---

## 10. 里程碑 × 模块映射

| 里程碑 | 新增模块 | 验收场景 |
|---|---|---|
| **M1** 跑起来 | core(Cpu/Loader/Memory)、bus、常量 TimeModel、USART(仅TX)、EventBus、cli | Keil 编的串口 hex 在终端打出 "Hello" |
| **M2** 点灯 | RCC(时钟树)、SysTick、GPIO、ExceptionEngine(基础)、devices/led、Net(数字) | 虚拟 LED 按延时闪烁 |
| **M3** 中断 | EXTI、NVIC 完整优先级/抢占、devices/button | 按键中断翻转 LED |
| **M4** 波形 | TIM 通用+高级、ADC、devices/scope、devices/pot；（可选）加权 TimeModel | 示波器看 PWM，旋钮调占空比 |
| **M5** 数据流 | DMA、SPI、I2C、devices/oled、DAC | ADC→DMA→OLED 显示数值 |
| **M6** RTOS | 无新芯片模块；补 SCB/PendSV/SVC 细节 + 大量测试 | FreeRTOS 双任务闪烁 + 串口输出 |
| **M7** 混合仿真 | ngspice_bridge、Net 电气化 | LED 真实压降/限流电阻发热、PWM 经 RC 滤波成直流 |

---

## 11. 技术选型

| 用途 | 选择 |
|---|---|
| 语言 | Python ≥ 3.11 |
| CPU 仿真 | unicorn（官方 pip 包，含 Python 绑定） |
| 寄存器表 | cmsis-svd（解析）+ tools/svd_gen.py（生成） |
| 固件加载 | intelhex（.hex）、pyelftools（.elf） |
| 测试 | pytest |
| CLI 输出 | rich |
| 混合仿真(M7) | PySpice + ngspice |
| GUI(M4 定) | FastAPI+浏览器 或 PySide6（引擎无感知，不影响本期决策） |

---

## 12. 风险清单（诚实版）

| # | 风险 | 等级 | 对策 |
|---|---|---|---|
| 1 | 异常引擎（NVIC 叠在 Unicorn 上）复杂 | 高 | 按 ARMv7-M 手册逐条实现；M3 先过 EXTI，M6 用 FreeRTOS 当期末考 |
| 2 | bit-band 不做则 HAL/RTOS 固件跑飞 | 高 | M1~M2 在 bus 层实现，纯地址数学 |
| 3 | MMIO 读副作用注入机制（Unicorn 钩子时序） | 中 | M1 用最小 USART 验证两个候选方案后定稿 |
| 4 | DMA 与外设交织（循环采样） | 中 | M5 专项测试集 |
| 5 | 时间片粒度 vs 速度 | 中 | 自适应切片（next_event），基准测试调参 |
| 6 | Unicorn M-class 边角怪癖（xPSR/非对齐等） | 低 | 遇一个测一个，测试兜底 |
| 7 | USB 外设行为复杂 | 低 | 可选末关卡，只做协议级设备模型（虚拟串口） |
