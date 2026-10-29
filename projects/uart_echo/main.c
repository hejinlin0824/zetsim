/* 实战 04：USART1 轮询回显（HAL 库函数版）
 * PA9 = TX，PA10 = RX。Web 终端输入的字符由 HAL_UART_Receive 收进来，
 * 再用 HAL_UART_Transmit 原样发回。
 */
#include "stm32f1xx_hal.h"

/* UART 句柄：HAL 风格的“一个外设一个句柄”。
 * 后面所有 HAL_UART_xxx 函数都通过它找到 USART1 和内部状态。 */
static UART_HandleTypeDef huart1;

static void uart_init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART1_CLK_ENABLE();

    /* 引脚：TX(PA9) 复用推挽交给 USART1；RX(PA10) 浮空输入。
     * 上一版手工算 CRH 位段（0x4B0），现在由 HAL_GPIO_Init 代劳。 */
    GPIO_InitTypeDef io = {0};
    io.Pin   = GPIO_PIN_9;
    io.Mode  = GPIO_MODE_AF_PP;       /* 复用推挽：引脚信号由 USART1 驱动 */
    io.Pull  = GPIO_NOPULL;
    io.Speed = GPIO_SPEED_FREQ_HIGH;  /* 串口高速信号 */
    HAL_GPIO_Init(GPIOA, &io);

    io.Pin  = GPIO_PIN_10;
    io.Mode = GPIO_MODE_INPUT;        /* 浮空输入 */
    io.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &io);

    /* 串口参数结构体：波特率/字长/停止位/校验一眼可读。
     * HAL_UART_Init 内部替你算 BRR 分频（时钟来自 SystemCoreClock = 8MHz）。 */
    huart1.Instance          = USART1;
    huart1.Init.BaudRate     = 115200;
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart1);           /* 内部写 CR1 的 UE|TE|RE 并启动收发 */
}

int main(void)
{
    static const char banner[] =
        "\r\nzetsim C project (HAL): USART1 echo ready. Type to echo.\r\n";

    HAL_Init();
    uart_init();

    /* 发启动横幅：HAL_UART_Transmit 阻塞直到整段发完（内部等 TXE/TC 标志）。 */
    HAL_UART_Transmit(&huart1, (const uint8_t *)banner, sizeof(banner) - 1U,
                      HAL_MAX_DELAY);

    while (1) {
        uint8_t ch = 0;
        /* 阻塞收一个字节：没有字符就一直等（HAL_MAX_DELAY 不超时）。 */
        if (HAL_UART_Receive(&huart1, &ch, 1U, HAL_MAX_DELAY) == HAL_OK) {
            HAL_UART_Transmit(&huart1, &ch, 1U, HAL_MAX_DELAY); /* 原样回显 */
        }
    }
}

/* HAL 的 1ms 时基由 SysTick 中断推进（见 startup.c 向量表第 15 项）。 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
