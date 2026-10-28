/* 实战 04：USART1 轮询回显
 * PA9 = TX，PA10 = RX。Web 终端输入的字符经过 RX 数据寄存器进入 MCU，
 * 固件再等待 TXE 并把字符写回 DR。
 */
#include "stm32f103.h"

#define REG32(addr) (*(volatile uint32_t *)(uintptr_t)(addr))
#define GPIOA_CRH  REG32(0x40010804u)
#define USART1_SR  REG32(0x40013800u)
#define USART1_DR  REG32(0x40013804u)
#define USART1_BRR REG32(0x40013808u)
#define USART1_CR1 REG32(0x4001380Cu)

static void uart_putc(char c)
{
    while ((USART1_SR & (1u << 7)) == 0u) { } /* TXE：DR 可写 */
    USART1_DR = (uint8_t)c;
}
static void uart_puts(const char *s)
{
    while (*s) uart_putc(*s++);
}
int main(void)
{
    RCC->APB2ENR |= (1u << 2) | (1u << 14); /* GPIOA + USART1 时钟 */
    GPIOA_CRH = (GPIOA_CRH & ~0xFFFu) | 0x4B0u; /* PA9 AF PP, PA10 浮空输入 */
    USART1_BRR = 0x0457u;                  /* 约 115200 baud @ 8MHz */
    USART1_CR1 = (1u << 13) | (1u << 3) | (1u << 2); /* UE|TE|RE */
    uart_puts("\r\nzetsim C project: USART1 echo ready. Type to echo.\r\n");

    while (1) {
        if (USART1_SR & (1u << 5)) {      /* RXNE：收到一个字节 */
            const char c = (char)USART1_DR; /* 读取 DR 清接收状态 */
            uart_putc(c);
        }
    }
}
