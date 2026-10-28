/*
 * Minimal C startup for the HAL beginner example.
 * Full Cortex-M core vector slots are present so SysTick uses vector 15.
 */
#include <stdint.h>

extern uint32_t _estack;
extern uint32_t _sidata, _sdata, _edata;
extern uint32_t _sbss, _ebss;

void SystemInit(void);
int main(void);
void SysTick_Handler(void);

static void Default_Handler(void)
{
    for (;;) { }
}

void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    uint32_t *dst;
    for (dst = &_sdata; dst < &_edata; )
        *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss; )
        *dst++ = 0U;

    SystemInit();
    (void)main();
    for (;;) { }
}

typedef void (*ISR_Handler)(void);
__attribute__((section(".isr_vector"), used))
ISR_Handler const vector_table[76] = {
    [0] = (ISR_Handler)&_estack,
    [1] = Reset_Handler,
    [2] = Default_Handler,  /* NMI */
    [3] = Default_Handler,  /* HardFault */
    [4] = Default_Handler,  /* MemManage */
    [5] = Default_Handler,  /* BusFault */
    [6] = Default_Handler,  /* UsageFault */
    [7] = 0, [8] = 0, [9] = 0, [10] = 0,
    [11] = Default_Handler, /* SVCall */
    [12] = Default_Handler, /* DebugMon */
    [13] = 0,
    [14] = Default_Handler, /* PendSV */
    [15] = SysTick_Handler,
    [16 ... 75] = Default_Handler
};
