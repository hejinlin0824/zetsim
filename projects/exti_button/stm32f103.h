/* ============================================================
 * stm32f103.h —— 只包含本项目用到的寄存器定义
 *
 * 学习要点：所有寄存器都是 volatile（每次都真读写内存，不被编译器
 * 优化掉）——这是裸机编程和写上位机程序最大的区别之一。
 * ============================================================ */
#ifndef STM32F103_H
#define STM32F103_H

#include <stdint.h>

/* ---- 复位与时钟控制器 RCC @ 0x40021000 ----
 * 每个外设都有自己的开关（使能位）。用哪个外设就要先开哪个时钟，
 * 这是 STM32 和 51 单片机最大的区别：默认一切关闭，省电。 */
typedef struct {
    volatile uint32_t CR;        /* 0x00 时钟控制   */
    volatile uint32_t CFGR;      /* 0x04 时钟配置   */
    volatile uint32_t CIR;       /* 0x08 中断标志   */
    volatile uint32_t APB2RSTR;  /* 0x0C APB2 复位  */
    volatile uint32_t APB1RSTR;  /* 0x10 APB1 复位  */
    volatile uint32_t AHBENR;    /* 0x14 AHB 使能   */
    volatile uint32_t APB2ENR;   /* 0x18 APB2 使能  ← GPIO 在这 */
    volatile uint32_t APB1ENR;   /* 0x1C APB1 使能  ← TIM2-7/USART2-5... */
    volatile uint32_t BDCR;      /* 0x20            */
    volatile uint32_t CSR;       /* 0x24            */
} RCC_t;

/* ---- 通用 IO 口 GPIO @ 0x40010800(A)...0x40011C00(E)... ----
 * CRL 管引脚 0~7，CRH 管引脚 8~15，每 4 位（半字节）配一个引脚：
 *   输出模式：MODE=10(2MHz)/11(50MHz) + CNF=00(推挽)
 *   => 通用推挽输出 2MHz = 0b0010 = 0x2 */
typedef struct {
    volatile uint32_t CRL;       /* 0x00 低 8 脚配置 */
    volatile uint32_t CRH;       /* 0x04 高 8 脚配置 */
    volatile uint32_t IDR;       /* 0x08 输入数据（读引脚电平） */
    volatile uint32_t ODR;       /* 0x0C 输出数据（写 1=高电平） */
    volatile uint32_t BSRR;      /* 0x10 置位/复位（原子操作） */
    volatile uint32_t BRR;       /* 0x14 复位 */
    volatile uint32_t LCKR;      /* 0x18 锁定 */
} GPIO_t;

/* ---- SysTick：内核自带的 24 位倒数定时器 @ 0xE000E010 ----
 * 为什么用它做延时？因为它不占任何外设资源，且和 CPU 同频，
 * 计数值和时间的换算最直观。 */
typedef struct {
    volatile uint32_t CTRL;      /* 0x00 bit0 使能 bit1 中断 bit2 时钟源 */
    volatile uint32_t LOAD;      /* 0x04 重装值（24 位最大 16777215） */
    volatile uint32_t VAL;       /* 0x08 当前值（读它不会干扰计数） */
    volatile uint32_t CALIB;     /* 0x0C 校准 */
} SysTick_t;

#define RCC     ((RCC_t    *)0x40021000u)
#define GPIOA   ((GPIO_t   *)0x40010800u)
#define GPIOB   ((GPIO_t   *)0x40010C00u)
#define GPIOC   ((GPIO_t   *)0x40011000u)
#define GPIOD   ((GPIO_t   *)0x40011400u)
#define GPIOE   ((GPIO_t   *)0x40011800u)
#define SysTick ((SysTick_t *)0xE000E010u)

#endif /* STM32F103_H */
