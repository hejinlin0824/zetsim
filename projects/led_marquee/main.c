/* ============================================================
 * 项目一：8-LED 跑马灯
 *
 * 电路连接（在网页原理图里照着连）：
 *     PA0..PA7 → 各自的 330Ω 限流电阻 → 对应 LED 正极
 *     所有 LED 负极 → GND
 *     限流电阻用于降低 LED 电流；不要把教学仿真的简化接法照搬到真实硬件。
 *
 * 学习目标：
 *   1. 开外设时钟（RCC）     —— STM32 的第一道门
 *   2. 配 GPIO 为输出（CRL） —— 每个引脚 4 位
 *   3. 用 SysTick 做精确延时 —— 内核定时器
 * ============================================================ */
#include "stm32f103.h"

/* 8 个灯接在 PA0~PA7。第 i 个灯 = ODR 的第 i 位写 1。
 * (1u << i)：把 1 左移 i 位 → 只有第 i 位是 1，其它全 0。*/
#define LED(i)      (1u << (i))

/* 一步走多快（毫秒）。改小它，灯跑得更快。*/
#define STEP_MS     100

/* ---- 初始化：开时钟 + 配引脚 ---- */
static void led_init(void)
{
    /* RCC_APB2ENR 的 bit2 = GPIOA 时钟使能。
     * 不开这一位，写 GPIOA 寄存器全都无效——这是新手最常踩的坑。*/
    RCC->APB2ENR |= (1u << 2);

    /* CRL 管的是 PA0~PA7 这 8 个脚，每 4 位一个：
     * 0x2 = 0b0010 = 通用推挽输出、速度 2MHz。
     * 8 个脚全配成输出 → 0x22222222，一个字搞定。*/
    GPIOA->CRL = 0x22222222u;

    /* 初始全灭（ODR 全 0 = 输出低电平 = 灯不亮）*/
    GPIOA->ODR = 0;
}

/* ---- 毫秒延时：SysTick 从 LOAD 值往 0 倒着数 ----
 * 电路没配 PLL 时芯片跑在内部 8MHz（HSI）→ 1ms = 8000 个时钟。
 * 数到 0 时 CTRL 的 bit16（COUNTFLAG）自动置 1。*/
static void delay_ms(uint32_t ms)
{
    SysTick->LOAD = 8000u * ms - 1u;   /* 要数的时钟个数      */
    SysTick->VAL  = 0;                 /* 清当前值，重新开始  */
    SysTick->CTRL = 0x5;               /* bit0 开启 + bit2 用 CPU 时钟 */
    while ((SysTick->CTRL & (1u << 16)) == 0)
        ;                              /* 空转到数完为止      */
    SysTick->CTRL = 0;                 /* 关掉，省得它再跑    */
}

/* ---- 主函数：上电后 C 世界的入口 ---- */
int main(void)
{
    uint32_t i = 0;

    led_init();

    /* 超级循环（super loop）：裸机程序永不返回 */
    while (1)
    {
        GPIOA->ODR = LED(i);           /* 只点亮第 i 个灯      */
        delay_ms(STEP_MS);             /* 停留一会儿           */
        i++;                           /* 挪到下一个灯         */
        if (i >= 8)                    /* 0→1→…→7→0 循环      */
            i = 0;                     /* （不用 % 8：避免除法）*/
    }
}
