/* ============================================================
 * startup.c —— 芯片上电后最先执行的代码（复位处理程序）
 *
 * 真实芯片复位时做了什么：
 *   1. 从 Flash 头部（0x08000000）读第 0 个字 → 设为栈顶指针 MSP
 *   2. 读第 1 个字 → 作为 PC 跳过去执行（= 下面的 Reset_Handler）
 *
 * C 语言能跑起来靠这里先做两件家务：
 *   .data：有初值的全局变量——从 Flash 搬到 RAM（RAM 掉电丢失）
 *   .bss ：没初值的全局变量——在 RAM 里清零（C 标准要求）
 * ============================================================ */
#include <stdint.h>

/* 这些符号由 link.ld 定义，标记各段的位置 */
extern uint32_t _estack;                 /* 栈顶（RAM 末尾）   */
extern uint32_t _sidata, _sdata, _edata; /* .data 的起点/终点  */
extern uint32_t _sbss, _ebss;            /* .bss  的起点/终点  */

int main(void);

void Reset_Handler(void)
{
    uint32_t *src, *dst;

    /* 1. 把 .data 段的初始值从 Flash 复制到 RAM */
    src = &_sidata;
    for (dst = &_sdata; dst < &_edata; )
        *dst++ = *src++;

    /* 2. 把 .bss 段清零 */
    for (dst = &_sbss; dst < &_ebss; )
        *dst++ = 0;

    /* 3. 进入 C 世界 */
    main();

    /* main 不应该返回；万一返回了就停在这里 */
    for (;;)
        ;
}

/* 向量表：PA0 对应 EXTI0，IRQ 编号 6，向量下标 = 16 + 6。 */
extern void EXTI0_IRQHandler(void);
__attribute__((section(".isr_vector"), used))
void (* const vector_table[23])(void) = {
    [0] = (void (*const)(void))&_estack,
    [1] = Reset_Handler,
    [22] = EXTI0_IRQHandler,
};
