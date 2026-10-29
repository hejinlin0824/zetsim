/* ============================================================
 * startup.c —— 芯片上电后最先执行的代码（复位处理程序）
 * HAL 库函数版启动文件；本项目使用 EXTI0 外部中断，
 * 所以把向量表第 22 项（IRQ6 = EXTI0 + 16）指到 EXTI0_IRQHandler。
 *
 * Reset_Handler 的家务：
 *   .data：有初值的全局变量——从 Flash 搬到 RAM（RAM 掉电丢失）
 *   .bss ：没初值的全局变量——在 RAM 里清零（C 标准要求）
 * 然后调用 SystemInit()（官方模板，F103xE 下为空实现）再进入 main()。
 * ============================================================ */
#include <stdint.h>

/* 这些符号由 link.ld 定义，标记各段的位置 */
extern uint32_t _estack;                 /* 栈顶（RAM 末尾）   */
extern uint32_t _sidata, _sdata, _edata; /* .data 的起点/终点  */
extern uint32_t _sbss, _ebss;            /* .bss  的起点/终点  */

void SystemInit(void);
int main(void);
void SysTick_Handler(void);
void EXTI0_IRQHandler(void);

static void Default_Handler(void)
{
    /* 没写处理函数的中断来了就停在这里，方便调试发现 */
    for (;;)
        ;
}

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

    /* 3. 初始化系统（官方模板）后进入 C 世界 */
    SystemInit();
    (void)main();

    /* main 不应该返回；万一返回了就停在这里 */
    for (;;)
        ;
}

/* 向量表：放在 Flash 最前面（链接脚本保证）。
 * 内核异常用 [0..15]，外设中断从 [16] 开始排：
 * EXTI0_IRQn = 6 → 向量表 [16 + 6] = [22]。
 * 写在范围填充之后，同名下标以后者为准。 */
typedef void (*ISR_Handler)(void);
__attribute__((section(".isr_vector"), used))
ISR_Handler const vector_table[76] = {
    (ISR_Handler)&_estack,   /* [0] 初始栈顶 MSP   */
    Reset_Handler,           /* [1] 复位           */
    Default_Handler,         /* [2] NMI            */
    Default_Handler,         /* [3] HardFault      */
    Default_Handler,         /* [4] MemManage      */
    Default_Handler,         /* [5] BusFault       */
    Default_Handler,         /* [6] UsageFault     */
    0, 0, 0, 0,              /* [7..10] 保留       */
    Default_Handler,         /* [11] SVCall        */
    Default_Handler,         /* [12] DebugMon      */
    0,                       /* [13] 保留          */
    Default_Handler,         /* [14] PendSV        */
    SysTick_Handler,         /* [15] SysTick：HAL 时基 */
    [16 ... 75] = Default_Handler,
    [22] = EXTI0_IRQHandler, /* EXTI0 中断入口     */
};
