/* ============================================================
 * link.ld —— 链接脚本：告诉链接器代码和数据各放哪儿
 *
 * STM32F103ZET6 的存储器地图（芯片手册固定死的）：
 *   Flash : 0x08000000 起，512K   —— 程序放这里（掉电不丢）
 *   SRAM  : 0x20000000 起，64K    —— 变量/栈放这里（掉电就没了）
 * ============================================================ */
ENTRY(Reset_Handler)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 64K
}

/* 栈顶 = RAM 末尾。ARM 的栈向下生长（先减后用），从最高地址开始。*/
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    /* 向量表必须位于 Flash 最开头（芯片复位时固定从这里取）*/
    .isr_vector :
    {
        KEEP(*(.isr_vector))
    } > FLASH

    /* 代码和常量 */
    .text :
    {
        *(.text*)          /* 所有函数            */
        *(.rodata*)        /* const 常量、字符串  */
        . = ALIGN(4);
    } > FLASH

    /* 有初值的全局变量：运行时在 RAM，初始值存在 Flash */
    .data :
    {
        _sdata = .;
        *(.data*)
        _edata = .;
    } > RAM AT > FLASH
    _sidata = LOADADDR(.data);   /* 初值在 Flash 里的存放地址 */

    /* 无初值的全局变量：只在 RAM，启动时清零 */
    .bss :
    {
        _sbss = .;
        *(.bss*)
        *(COMMON)
        _ebss = .;
    } > RAM
}
