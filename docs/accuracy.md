# zetsim 精度看板

> 回答一个问题：**这台仿真器有多准？** 每一行都有测试编号背书（`pytest tests/ -v` 可复现）。

## 1. 验证矩阵

| 能力 | 验证方式 | 结果 | 测试 |
|---|---|---|---|
| 汇编器编码正确性 | 每条指令在 Unicorn 中执行预言 | 10/10 编码全对 | test_asm.py |
| 固件加载（hex/elf/向量表） | intel hex 往返 | 通过 | test_asm.py |
| USART1 轮询发送 | 固件发 "Hello, zetsim!" | 字节精确一致 | test_m1_m2.py |
| 波特率（BRR 公式） | 8MHz/115200=69.4375 分频 | 解析精确 | test_m1_m2.py |
| NVIC 异常入口/出口 | SysTick 1ms 中断翻转 PA5 | 中位周期误差 <10% | test_m1_m2.py |
| WFI 睡眠快进 | 50ms 仿真墙钟 <10s | 实际 <0.1s | test_m1_m2.py |
| EXTI 按键中断 | 5.000ms 注入按键 | 翻转时刻 4.9-5.2ms | test_m3.py |
| NVIC 使能/禁能 | ISER 清零 | pending 但不进入 | test_m3.py |
| 优先级抢占 | SysTick(prio0) vs EXTI0(prio5) | 抢占发生在 handler 窗口内 | test_m3.py |
| TIM2 PWM | psc=7/arr=99/ccr=30 | 频率 10kHz±5%，占空比 30%±3% | test_m4.py |
| ADC 采样 | 2.5V → 3098 | 误差 <±30 LSB | test_m4.py |
| ADC 连续+跟随 | 0.8V→2.0V 电位器 | 跟随正确 | test_m4.py |
| DMA 循环搬运 | ADC→512 缓冲，中途变电压 | 前段 2482/后段 1241，CNDTR 正确回卷 | test_m5.py |
| SPI 主收发 | 3 字节发送读回 | TX=[0xA0,0xA1,0xA2]，读回=0xA2 | test_m5.py |
| I2C 主发送+OLED | RM0008 轮询流程完整初始化 SSD1306 | 22 命令+32 数据字节全部到达，像素=128 | test_m5.py |
| DAC 输出 | DHR12R1=2048 | PA4=1.65V±0.01，DOR=2048 | test_m5.py |
| PendSV 上下文切换 | FreeRTOS 式双任务+PSP+EXC_RETURN 0xFFFFFFFD | 双任务交错运行，SVC 计数≥3 | test_m6.py |
| RC 低通滤波 | 10kHz/30% PWM → 1kΩ+100nF | 平均 0.99V±0.12V，纹波 <1.5V | test_m7.py |
| LED 电气 | 3.3V→LED→220Ω | Vf 1.7-2.7V，I>2mA，关断 <1nA | test_m7.py |
| 寄存器地图 | 30 个模型基址 vs 官方 SVD | 全部一致（还真抓出过 5 个手写错址） | test_regmap.py |
| 原理图网表 | union-find 提取 + 动态接线 | 网络/引脚归属正确 | test_m8.py |
| 画布 LED 直连 | PA5—LED—GND 数字驱动 | 随 ODR 即时亮灭 | test_m8.py |
| 画布串阻 LED | PA5—220Ω—LED—GND | SPICE 电流 2-20mA、拉低熄灭 | test_m8.py |
| 画布按键中断 | 原理图按键→EXTI→固件 | 4ms 注入 4-5ms 翻转 | test_m8.py |
| 画布 RC 探针 | PWM—1k—100n + 探针 | 平均 0.99V±0.15V | test_m8.py |

## 2. 时间精度分层

| 层级 | 精度 | 机制 |
|---|---|---|
| 外设周期（PWM 频率、波特率、SysTick、ADC 转换时间） | **解析精确** | 时钟树实时解析 RCC + 事件驱动步进 |
| 中断延迟 | 微秒级 | 时间片 + next_event 自适应收缩 |
| CPU 软件延时（忙等循环） | ±30~50% | 常数 CPI=2.0 模型（可 `--cpi` 调） |

## 3. 已知简化（教学场景无感）

- TIM：ARPE/CCR 预装载、重复计数器 RCR、输入捕获、中央对齐/向下计数未建模；
  PWM 输出仅默认 AF 引脚映射（无 remap）
- ADC：注入组、看门狗、采样时间选择（固定按 1.5+12.5 周期）、双 ADC 同步
- I2C：主接收、10 位地址、时钟拉伸（协议时序按即时完成处理）
- SPI：仅主模式；MISO 默认回环（可挂器件 reply()）
- DMA：传输即时完成（burst 语义），无 FIFO/突发长度
- 内核：IPSR 读值恒 0；EPSR/IT 块细节、非对齐访问的精确 fault 行为未建模
- Flash：等待周期/预取对时序的影响（并入 CPI 近似）
- USB/CAN/SDIO/FSMC/RTC/BKP/PWR：存根（读 0、写告警一次）

## 4. 复现

```bash
cd zetsim
python -m pytest tests/ -v        # 30 项
```
