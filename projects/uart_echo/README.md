# 实战 04：USART1 串口回显

## 接线 / 外设约定
- PA9：USART1_TX（Web 终端显示发出的字节）
- PA10：USART1_RX（Web 终端输入注入到芯片）
- 默认 HSI 8MHz，HAL_UART_Init 按 SystemCoreClock 自动计算 BRR，115200 baud

## 学习目标
理解 HAL 时钟宏、GPIO 复用模式（GPIO_MODE_AF_PP）、HAL_UART_Init 参数结构与 HAL_UART_Transmit / HAL_UART_Receive 阻塞式轮询收发。

## 动手任务
1. 编译并运行，在 USART1 输入框发送 `hello`。
2. 修改启动问候语后重新编译。
3. 把 `HAL_UART_Receive` 的超时从 HAL_MAX_DELAY 改成 1ms，配合返回值观察轮询与阻塞的差别。
4. 尝试一次发送 20 个字符，确认终端仍能持续交互。

## 验收
启动后看到固件自己的问候语；输入字符后获得固件逐字节回显。当前为阻塞轮询版，不依赖 USART 中断向量。
