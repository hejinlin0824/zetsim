# STM32F103 寄存器速查（SVD 自动生成）

来源: modm-io/cmsis-svd-stm32 (Apache-2.0)，经 `tools/svd_gen.py` 生成。

## ADC1 — `0x40012400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| SR | `0x0000` | status register |
| CR1 | `0x0004` | control register 1 |
| CR2 | `0x0008` | control register 2 |
| SMPR1 | `0x000c` | sample time register 1 |
| SMPR2 | `0x0010` | sample time register 2 |
| JOFR1 | `0x0014` | injected channel data offset register |
| JOFR2 | `0x0018` | injected channel data offset register |
| JOFR3 | `0x001c` | injected channel data offset register |
| JOFR4 | `0x0020` | injected channel data offset register |
| HTR | `0x0024` | watchdog higher threshold |
| LTR | `0x0028` | watchdog lower threshold |
| SQR1 | `0x002c` | regular sequence register 1 |
| SQR2 | `0x0030` | regular sequence register 2 |
| SQR3 | `0x0034` | regular sequence register 3 |
| JSQR | `0x0038` | injected sequence register |
| JDR1 | `0x003c` | injected data register x |
| JDR2 | `0x0040` | injected data register x |
| JDR3 | `0x0044` | injected data register x |
| JDR4 | `0x0048` | injected data register x |
| DR | `0x004c` | regular data register |

## ADC2 — `0x40012800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| SR | `0x0000` | status register |
| CR1 | `0x0004` | control register 1 |
| CR2 | `0x0008` | control register 2 |
| SMPR1 | `0x000c` | sample time register 1 |
| SMPR2 | `0x0010` | sample time register 2 |
| JOFR1 | `0x0014` | injected channel data offset register |
| JOFR2 | `0x0018` | injected channel data offset register |
| JOFR3 | `0x001c` | injected channel data offset register |
| JOFR4 | `0x0020` | injected channel data offset register |
| HTR | `0x0024` | watchdog higher threshold |
| LTR | `0x0028` | watchdog lower threshold |
| SQR1 | `0x002c` | regular sequence register 1 |
| SQR2 | `0x0030` | regular sequence register 2 |
| SQR3 | `0x0034` | regular sequence register 3 |
| JSQR | `0x0038` | injected sequence register |
| JDR1 | `0x003c` | injected data register x |
| JDR2 | `0x0040` | injected data register x |
| JDR3 | `0x0044` | injected data register x |
| JDR4 | `0x0048` | injected data register x |
| DR | `0x004c` | regular data register |

## ADC3 — `0x40013c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## AFIO — `0x40010000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| EVCR | `0x0000` | Event Control Register |
| MAPR | `0x0004` | AF remap and debug I/O configuration |
| EXTICR1 | `0x0008` | External interrupt configuration register 1 |
| EXTICR2 | `0x000c` | External interrupt configuration register 2 |
| EXTICR3 | `0x0010` | External interrupt configuration register 3 |
| EXTICR4 | `0x0014` | External interrupt configuration register 4 |
| MAPR2 | `0x001c` | AF remap and debug I/O configuration |

## BKP — `0x40006c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| DR1 | `0x0000` | Backup data register (BKP_DR) |
| DR2 | `0x0004` | Backup data register (BKP_DR) |
| DR3 | `0x0008` | Backup data register (BKP_DR) |
| DR4 | `0x000c` | Backup data register (BKP_DR) |
| DR5 | `0x0010` | Backup data register (BKP_DR) |
| DR6 | `0x0014` | Backup data register (BKP_DR) |
| DR7 | `0x0018` | Backup data register (BKP_DR) |
| DR8 | `0x001c` | Backup data register (BKP_DR) |
| DR9 | `0x0020` | Backup data register (BKP_DR) |
| DR10 | `0x0024` | Backup data register (BKP_DR) |
| RTCCR | `0x0028` | RTC clock calibration register |
| CR | `0x002c` | Backup control register |
| CSR | `0x0030` | BKP_CSR control/status register |
| DR11 | `0x003c` | Backup data register (BKP_DR) |
| DR12 | `0x0040` | Backup data register (BKP_DR) |
| DR13 | `0x0044` | Backup data register (BKP_DR) |
| DR14 | `0x0048` | Backup data register (BKP_DR) |
| DR15 | `0x004c` | Backup data register (BKP_DR) |
| DR16 | `0x0050` | Backup data register (BKP_DR) |
| DR17 | `0x0054` | Backup data register (BKP_DR) |
| DR18 | `0x0058` | Backup data register (BKP_DR) |
| DR19 | `0x005c` | Backup data register (BKP_DR) |
| DR20 | `0x0060` | Backup data register (BKP_DR) |
| DR21 | `0x0064` | Backup data register (BKP_DR) |
| DR22 | `0x0068` | Backup data register (BKP_DR) |
| DR23 | `0x006c` | Backup data register (BKP_DR) |
| DR24 | `0x0070` | Backup data register (BKP_DR) |
| DR25 | `0x0074` | Backup data register (BKP_DR) |
| DR26 | `0x0078` | Backup data register (BKP_DR) |
| DR27 | `0x007c` | Backup data register (BKP_DR) |
| DR28 | `0x0080` | Backup data register (BKP_DR) |
| DR29 | `0x0084` | Backup data register (BKP_DR) |
| DR30 | `0x0088` | Backup data register (BKP_DR) |
| DR31 | `0x008c` | Backup data register (BKP_DR) |
| DR32 | `0x0090` | Backup data register (BKP_DR) |
| DR33 | `0x0094` | Backup data register (BKP_DR) |
| DR34 | `0x0098` | Backup data register (BKP_DR) |
| DR35 | `0x009c` | Backup data register (BKP_DR) |
| DR36 | `0x00a0` | Backup data register (BKP_DR) |
| DR37 | `0x00a4` | Backup data register (BKP_DR) |
| DR38 | `0x00a8` | Backup data register (BKP_DR) |
| DR39 | `0x00ac` | Backup data register (BKP_DR) |
| DR40 | `0x00b0` | Backup data register (BKP_DR) |
| DR41 | `0x00b4` | Backup data register (BKP_DR) |
| DR42 | `0x00b8` | Backup data register (BKP_DR) |

## CAN1 — `0x40006400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CAN_MCR | `0x0000` | CAN_MCR |
| CAN_MSR | `0x0004` | CAN_MSR |
| CAN_TSR | `0x0008` | CAN_TSR |
| CAN_RF0R | `0x000c` | CAN_RF0R |
| CAN_RF1R | `0x0010` | CAN_RF1R |
| CAN_IER | `0x0014` | CAN_IER |
| CAN_ESR | `0x0018` | CAN_ESR |
| CAN_BTR | `0x001c` | CAN_BTR |
| CAN_TI0R | `0x0180` | CAN_TI0R |
| CAN_TDT0R | `0x0184` | CAN_TDT0R |
| CAN_TDL0R | `0x0188` | CAN_TDL0R |
| CAN_TDH0R | `0x018c` | CAN_TDH0R |
| CAN_TI1R | `0x0190` | CAN_TI1R |
| CAN_TDT1R | `0x0194` | CAN_TDT1R |
| CAN_TDL1R | `0x0198` | CAN_TDL1R |
| CAN_TDH1R | `0x019c` | CAN_TDH1R |
| CAN_TI2R | `0x01a0` | CAN_TI2R |
| CAN_TDT2R | `0x01a4` | CAN_TDT2R |
| CAN_TDL2R | `0x01a8` | CAN_TDL2R |
| CAN_TDH2R | `0x01ac` | CAN_TDH2R |
| CAN_RI0R | `0x01b0` | CAN_RI0R |
| CAN_RDT0R | `0x01b4` | CAN_RDT0R |
| CAN_RDL0R | `0x01b8` | CAN_RDL0R |
| CAN_RDH0R | `0x01bc` | CAN_RDH0R |
| CAN_RI1R | `0x01c0` | CAN_RI1R |
| CAN_RDT1R | `0x01c4` | CAN_RDT1R |
| CAN_RDL1R | `0x01c8` | CAN_RDL1R |
| CAN_RDH1R | `0x01cc` | CAN_RDH1R |
| CAN_FMR | `0x0200` | CAN_FMR |
| CAN_FM1R | `0x0204` | CAN_FM1R |
| CAN_FS1R | `0x020c` | CAN_FS1R |
| CAN_FFA1R | `0x0214` | CAN_FFA1R |
| CAN_FA1R | `0x021c` | CAN_FA1R |
| F0R1 | `0x0240` | Filter bank 0 register 1 |
| F0R2 | `0x0244` | Filter bank 0 register 2 |
| F1R1 | `0x0248` | Filter bank 1 register 1 |
| F1R2 | `0x024c` | Filter bank 1 register 2 |
| F2R1 | `0x0250` | Filter bank 2 register 1 |
| F2R2 | `0x0254` | Filter bank 2 register 2 |
| F3R1 | `0x0258` | Filter bank 3 register 1 |
| F3R2 | `0x025c` | Filter bank 3 register 2 |
| F4R1 | `0x0260` | Filter bank 4 register 1 |
| F4R2 | `0x0264` | Filter bank 4 register 2 |
| F5R1 | `0x0268` | Filter bank 5 register 1 |
| F5R2 | `0x026c` | Filter bank 5 register 2 |
| F6R1 | `0x0270` | Filter bank 6 register 1 |
| F6R2 | `0x0274` | Filter bank 6 register 2 |
| F7R1 | `0x0278` | Filter bank 7 register 1 |
| F7R2 | `0x027c` | Filter bank 7 register 2 |
| F8R1 | `0x0280` | Filter bank 8 register 1 |
| F8R2 | `0x0284` | Filter bank 8 register 2 |
| F9R1 | `0x0288` | Filter bank 9 register 1 |
| F9R2 | `0x028c` | Filter bank 9 register 2 |
| F10R1 | `0x0290` | Filter bank 10 register 1 |
| F10R2 | `0x0294` | Filter bank 10 register 2 |
| F11R1 | `0x0298` | Filter bank 11 register 1 |
| F11R2 | `0x029c` | Filter bank 11 register 2 |
| F12R1 | `0x02a0` | Filter bank 4 register 1 |
| F12R2 | `0x02a4` | Filter bank 12 register 2 |
| F13R1 | `0x02a8` | Filter bank 13 register 1 |
| F13R2 | `0x02ac` | Filter bank 13 register 2 |

## CAN2 — `0x40006800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## CRC — `0x40023000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| DR | `0x0000` | Data register |
| IDR | `0x0004` | Independent Data register |
| CR | `0x0008` | Control register |

## DAC — `0x40007400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR | `0x0000` | Control register (DAC_CR) |
| SWTRIGR | `0x0004` | DAC software trigger register |
| DHR12R1 | `0x0008` | DAC channel1 12-bit right-aligned data |
| DHR12L1 | `0x000c` | DAC channel1 12-bit left aligned data |
| DHR8R1 | `0x0010` | DAC channel1 8-bit right aligned data |
| DHR12R2 | `0x0014` | DAC channel2 12-bit right aligned data |
| DHR12L2 | `0x0018` | DAC channel2 12-bit left aligned data |
| DHR8R2 | `0x001c` | DAC channel2 8-bit right-aligned data |
| DHR12RD | `0x0020` | Dual DAC 12-bit right-aligned data holding |
| DHR12LD | `0x0024` | DUAL DAC 12-bit left aligned data holding |
| DHR8RD | `0x0028` | DUAL DAC 8-bit right aligned data holding |
| DOR1 | `0x002c` | DAC channel1 data output register |
| DOR2 | `0x0030` | DAC channel2 data output register |

## DBG — `0xe0042000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| IDCODE | `0x0000` | DBGMCU_IDCODE |
| CR | `0x0004` | DBGMCU_CR |

## DMA1 — `0x40020000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| ISR | `0x0000` | DMA interrupt status register |
| IFCR | `0x0004` | DMA interrupt flag clear register |
| CCR1 | `0x0008` | DMA channel configuration register |
| CNDTR1 | `0x000c` | DMA channel 1 number of data |
| CPAR1 | `0x0010` | DMA channel 1 peripheral address |
| CMAR1 | `0x0014` | DMA channel 1 memory address |
| CCR2 | `0x001c` | DMA channel configuration register |
| CNDTR2 | `0x0020` | DMA channel 2 number of data |
| CPAR2 | `0x0024` | DMA channel 2 peripheral address |
| CMAR2 | `0x0028` | DMA channel 2 memory address |
| CCR3 | `0x0030` | DMA channel configuration register |
| CNDTR3 | `0x0034` | DMA channel 3 number of data |
| CPAR3 | `0x0038` | DMA channel 3 peripheral address |
| CMAR3 | `0x003c` | DMA channel 3 memory address |
| CCR4 | `0x0044` | DMA channel configuration register |
| CNDTR4 | `0x0048` | DMA channel 4 number of data |
| CPAR4 | `0x004c` | DMA channel 4 peripheral address |
| CMAR4 | `0x0050` | DMA channel 4 memory address |
| CCR5 | `0x0058` | DMA channel configuration register |
| CNDTR5 | `0x005c` | DMA channel 5 number of data |
| CPAR5 | `0x0060` | DMA channel 5 peripheral address |
| CMAR5 | `0x0064` | DMA channel 5 memory address |
| CCR6 | `0x006c` | DMA channel configuration register |
| CNDTR6 | `0x0070` | DMA channel 6 number of data |
| CPAR6 | `0x0074` | DMA channel 6 peripheral address |
| CMAR6 | `0x0078` | DMA channel 6 memory address |
| CCR7 | `0x0080` | DMA channel configuration register |
| CNDTR7 | `0x0084` | DMA channel 7 number of data |
| CPAR7 | `0x0088` | DMA channel 7 peripheral address |
| CMAR7 | `0x008c` | DMA channel 7 memory address |

## DMA2 — `0x40020400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## ETHERNET_DMA — `0x40029000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| DMABMR | `0x0000` | Ethernet DMA bus mode register |
| DMATPDR | `0x0004` | Ethernet DMA transmit poll demand |
| DMARPDR | `0x0008` | EHERNET DMA receive poll demand |
| DMARDLAR | `0x000c` | Ethernet DMA receive descriptor list address |
| DMATDLAR | `0x0010` | Ethernet DMA transmit descriptor list |
| DMASR | `0x0014` | Ethernet DMA status register |
| DMAOMR | `0x0018` | Ethernet DMA operation mode |
| DMAIER | `0x001c` | Ethernet DMA interrupt enable |
| DMAMFBOCR | `0x0020` | Ethernet DMA missed frame and buffer |
| DMACHTDR | `0x0048` | Ethernet DMA current host transmit |
| DMACHRDR | `0x004c` | Ethernet DMA current host receive descriptor |
| DMACHTBAR | `0x0050` | Ethernet DMA current host transmit buffer |
| DMACHRBAR | `0x0054` | Ethernet DMA current host receive buffer |

## ETHERNET_MAC — `0x40028000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| MACCR | `0x0000` | Ethernet MAC configuration register |
| MACFFR | `0x0004` | Ethernet MAC frame filter register |
| MACHTHR | `0x0008` | Ethernet MAC hash table high |
| MACHTLR | `0x000c` | Ethernet MAC hash table low |
| MACMIIAR | `0x0010` | Ethernet MAC MII address register |
| MACMIIDR | `0x0014` | Ethernet MAC MII data register |
| MACFCR | `0x0018` | Ethernet MAC flow control register |
| MACVLANTR | `0x001c` | Ethernet MAC VLAN tag register |
| MACRWUFFR | `0x0028` | Ethernet MAC remote wakeup frame filter |
| MACPMTCSR | `0x002c` | Ethernet MAC PMT control and status register |
| MACSR | `0x0038` | Ethernet MAC interrupt status register |
| MACIMR | `0x003c` | Ethernet MAC interrupt mask register |
| MACA0HR | `0x0040` | Ethernet MAC address 0 high register |
| MACA0LR | `0x0044` | Ethernet MAC address 0 low |
| MACA1HR | `0x0048` | Ethernet MAC address 1 high register |
| MACA1LR | `0x004c` | Ethernet MAC address1 low |
| MACA2HR | `0x0050` | Ethernet MAC address 2 high register |
| MACA2LR | `0x0054` | Ethernet MAC address 2 low |
| MACA3HR | `0x0058` | Ethernet MAC address 3 high register |
| MACA3LR | `0x005c` | Ethernet MAC address 3 low |

## ETHERNET_MMC — `0x40028100`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| MMCCR | `0x0000` | Ethernet MMC control register |
| MMCRIR | `0x0004` | Ethernet MMC receive interrupt register |
| MMCTIR | `0x0008` | Ethernet MMC transmit interrupt register |
| MMCRIMR | `0x000c` | Ethernet MMC receive interrupt mask register |
| MMCTIMR | `0x0010` | Ethernet MMC transmit interrupt mask |
| MMCTGFSCCR | `0x004c` | Ethernet MMC transmitted good frames after a |
| MMCTGFMSCCR | `0x0050` | Ethernet MMC transmitted good frames after |
| MMCTGFCR | `0x0068` | Ethernet MMC transmitted good frames counter |
| MMCRFCECR | `0x0094` | Ethernet MMC received frames with CRC error |
| MMCRFAECR | `0x0098` | Ethernet MMC received frames with alignment |
| MMCRGUFCR | `0x00c4` | MMC received good unicast frames counter |

## ETHERNET_PTP — `0x40028700`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| PTPTSCR | `0x0000` | Ethernet PTP time stamp control register |
| PTPSSIR | `0x0004` | Ethernet PTP subsecond increment |
| PTPTSHR | `0x0008` | Ethernet PTP time stamp high |
| PTPTSLR | `0x000c` | Ethernet PTP time stamp low register |
| PTPTSHUR | `0x0010` | Ethernet PTP time stamp high update |
| PTPTSLUR | `0x0014` | Ethernet PTP time stamp low update register |
| PTPTSAR | `0x0018` | Ethernet PTP time stamp addend |
| PTPTTHR | `0x001c` | Ethernet PTP target time high |
| PTPTTLR | `0x0020` | Ethernet PTP target time low |

## EXTI — `0x40010400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| IMR | `0x0000` | Interrupt mask register |
| EMR | `0x0004` | Event mask register (EXTI_EMR) |
| RTSR | `0x0008` | Rising Trigger selection register |
| FTSR | `0x000c` | Falling Trigger selection register |
| SWIER | `0x0010` | Software interrupt event register |
| PR | `0x0014` | Pending register (EXTI_PR) |

## FLASH — `0x40022000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| ACR | `0x0000` | Flash access control register |
| KEYR | `0x0004` | Flash key register |
| OPTKEYR | `0x0008` | Flash option key register |
| SR | `0x000c` | Status register |
| CR | `0x0010` | Control register |
| AR | `0x0014` | Flash address register |
| OBR | `0x001c` | Option byte register |
| WRPR | `0x0020` | Write protection register |

## FSMC — `0xa0000000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| BCR1 | `0x0000` | SRAM/NOR-Flash chip-select control register |
| BTR1 | `0x0004` | SRAM/NOR-Flash chip-select timing register |
| BCR2 | `0x0008` | SRAM/NOR-Flash chip-select control register |
| BTR2 | `0x000c` | SRAM/NOR-Flash chip-select timing register |
| BCR3 | `0x0010` | SRAM/NOR-Flash chip-select control register |
| BTR3 | `0x0014` | SRAM/NOR-Flash chip-select timing register |
| BCR4 | `0x0018` | SRAM/NOR-Flash chip-select control register |
| BTR4 | `0x001c` | SRAM/NOR-Flash chip-select timing register |
| PCR2 | `0x0060` | PC Card/NAND Flash control register |
| SR2 | `0x0064` | FIFO status and interrupt register |
| PMEM2 | `0x0068` | Common memory space timing register |
| PATT2 | `0x006c` | Attribute memory space timing register |
| ECCR2 | `0x0074` | ECC result register 2 |
| PCR3 | `0x0080` | PC Card/NAND Flash control register |
| SR3 | `0x0084` | FIFO status and interrupt register |
| PMEM3 | `0x0088` | Common memory space timing register |
| PATT3 | `0x008c` | Attribute memory space timing register |
| ECCR3 | `0x0094` | ECC result register 3 |
| PCR4 | `0x00a0` | PC Card/NAND Flash control register |
| SR4 | `0x00a4` | FIFO status and interrupt register |
| PMEM4 | `0x00a8` | Common memory space timing register |
| PATT4 | `0x00ac` | Attribute memory space timing register |
| PIO4 | `0x00b0` | I/O space timing register 4 |
| BWTR1 | `0x0104` | SRAM/NOR-Flash write timing registers |
| BWTR2 | `0x010c` | SRAM/NOR-Flash write timing registers |
| BWTR3 | `0x0114` | SRAM/NOR-Flash write timing registers |
| BWTR4 | `0x011c` | SRAM/NOR-Flash write timing registers |

## GPIOA — `0x40010800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CRL | `0x0000` | Port configuration register low |
| CRH | `0x0004` | Port configuration register high |
| IDR | `0x0008` | Port input data register |
| ODR | `0x000c` | Port output data register |
| BSRR | `0x0010` | Port bit set/reset register |
| BRR | `0x0014` | Port bit reset register |
| LCKR | `0x0018` | Port configuration lock |

## GPIOB — `0x40010c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## GPIOC — `0x40011000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## GPIOD — `0x40011400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## GPIOE — `0x40011800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## GPIOF — `0x40011c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## GPIOG — `0x40012000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## I2C1 — `0x40005400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR1 | `0x0000` | Control register 1 |
| CR2 | `0x0004` | Control register 2 |
| OAR1 | `0x0008` | Own address register 1 |
| OAR2 | `0x000c` | Own address register 2 |
| DR | `0x0010` | Data register |
| SR1 | `0x0014` | Status register 1 |
| SR2 | `0x0018` | Status register 2 |
| CCR | `0x001c` | Clock control register |
| TRISE | `0x0020` | TRISE register |

## I2C2 — `0x40005800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## IWDG — `0x40003000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| KR | `0x0000` | Key register (IWDG_KR) |
| PR | `0x0004` | Prescaler register (IWDG_PR) |
| RLR | `0x0008` | Reload register (IWDG_RLR) |
| SR | `0x000c` | Status register (IWDG_SR) |

## MPU — `0xe000ed90`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| MPU_TYPER | `0x0000` | MPU type register |
| MPU_CTRL | `0x0004` | MPU control register |
| MPU_RNR | `0x0008` | MPU region number register |
| MPU_RBAR | `0x000c` | MPU region base address |
| MPU_RASR | `0x0010` | MPU region attribute and size |

## NVIC — `0xe000e100`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| ISER0 | `0x0000` | Interrupt Set-Enable Register |
| ISER1 | `0x0004` | Interrupt Set-Enable Register |
| ICER0 | `0x0080` | Interrupt Clear-Enable |
| ICER1 | `0x0084` | Interrupt Clear-Enable |
| ISPR0 | `0x0100` | Interrupt Set-Pending Register |
| ISPR1 | `0x0104` | Interrupt Set-Pending Register |
| ICPR0 | `0x0180` | Interrupt Clear-Pending |
| ICPR1 | `0x0184` | Interrupt Clear-Pending |
| IABR0 | `0x0200` | Interrupt Active Bit Register |
| IABR1 | `0x0204` | Interrupt Active Bit Register |
| IPR0 | `0x0300` | Interrupt Priority Register |
| IPR1 | `0x0304` | Interrupt Priority Register |
| IPR2 | `0x0308` | Interrupt Priority Register |
| IPR3 | `0x030c` | Interrupt Priority Register |
| IPR4 | `0x0310` | Interrupt Priority Register |
| IPR5 | `0x0314` | Interrupt Priority Register |
| IPR6 | `0x0318` | Interrupt Priority Register |
| IPR7 | `0x031c` | Interrupt Priority Register |
| IPR8 | `0x0320` | Interrupt Priority Register |
| IPR9 | `0x0324` | Interrupt Priority Register |
| IPR10 | `0x0328` | Interrupt Priority Register |
| IPR11 | `0x032c` | Interrupt Priority Register |
| IPR12 | `0x0330` | Interrupt Priority Register |
| IPR13 | `0x0334` | Interrupt Priority Register |
| IPR14 | `0x0338` | Interrupt Priority Register |

## NVIC_STIR — `0xe000ef00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| STIR | `0x0000` | Software trigger interrupt |

## OTG_FS_DEVICE — `0x50000800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| FS_DCFG | `0x0000` | OTG_FS device configuration register |
| FS_DCTL | `0x0004` | OTG_FS device control register |
| FS_DSTS | `0x0008` | OTG_FS device status register |
| FS_DIEPMSK | `0x0010` | OTG_FS device IN endpoint common interrupt |
| FS_DOEPMSK | `0x0014` | OTG_FS device OUT endpoint common interrupt |
| FS_DAINT | `0x0018` | OTG_FS device all endpoints interrupt |
| FS_DAINTMSK | `0x001c` | OTG_FS all endpoints interrupt mask register |
| DVBUSDIS | `0x0028` | OTG_FS device VBUS discharge time |
| DVBUSPULSE | `0x002c` | OTG_FS device VBUS pulsing time |
| DIEPEMPMSK | `0x0034` | OTG_FS device IN endpoint FIFO empty |
| FS_DIEPCTL0 | `0x0100` | OTG_FS device control IN endpoint 0 control |
| DIEPINT0 | `0x0108` | device endpoint-x interrupt |
| DIEPTSIZ0 | `0x0110` | device endpoint-0 transfer size |
| DTXFSTS0 | `0x0118` | OTG_FS device IN endpoint transmit FIFO |
| DIEPCTL1 | `0x0120` | OTG device endpoint-1 control |
| DIEPINT1 | `0x0128` | device endpoint-1 interrupt |
| DIEPTSIZ1 | `0x0130` | device endpoint-1 transfer size |
| DTXFSTS1 | `0x0138` | OTG_FS device IN endpoint transmit FIFO |
| DIEPCTL2 | `0x0140` | OTG device endpoint-2 control |
| DIEPINT2 | `0x0148` | device endpoint-2 interrupt |
| DIEPTSIZ2 | `0x0150` | device endpoint-2 transfer size |
| DTXFSTS2 | `0x0158` | OTG_FS device IN endpoint transmit FIFO |
| DIEPCTL3 | `0x0160` | OTG device endpoint-3 control |
| DIEPINT3 | `0x0168` | device endpoint-3 interrupt |
| DIEPTSIZ3 | `0x0170` | device endpoint-3 transfer size |
| DTXFSTS3 | `0x0178` | OTG_FS device IN endpoint transmit FIFO |
| DOEPCTL0 | `0x0300` | device endpoint-0 control |
| DOEPINT0 | `0x0308` | device endpoint-0 interrupt |
| DOEPTSIZ0 | `0x0310` | device OUT endpoint-0 transfer size |
| DOEPCTL1 | `0x0320` | device endpoint-1 control |
| DOEPINT1 | `0x0328` | device endpoint-1 interrupt |
| DOEPTSIZ1 | `0x0330` | device OUT endpoint-1 transfer size |
| DOEPCTL2 | `0x0340` | device endpoint-2 control |
| DOEPINT2 | `0x0348` | device endpoint-2 interrupt |
| DOEPTSIZ2 | `0x0350` | device OUT endpoint-2 transfer size |
| DOEPCTL3 | `0x0360` | device endpoint-3 control |
| DOEPINT3 | `0x0368` | device endpoint-3 interrupt |
| DOEPTSIZ3 | `0x0370` | device OUT endpoint-3 transfer size |

## OTG_FS_GLOBAL — `0x50000000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| FS_GOTGCTL | `0x0000` | OTG_FS control and status register |
| FS_GOTGINT | `0x0004` | OTG_FS interrupt register |
| FS_GAHBCFG | `0x0008` | OTG_FS AHB configuration register |
| FS_GUSBCFG | `0x000c` | OTG_FS USB configuration register |
| FS_GRSTCTL | `0x0010` | OTG_FS reset register |
| FS_GINTSTS | `0x0014` | OTG_FS core interrupt register |
| FS_GINTMSK | `0x0018` | OTG_FS interrupt mask register |
| FS_GRXSTSR_Device | `0x001c` | OTG_FS Receive status debug read(Device |
| FS_GRXSTSR_Host | `0x001c` | OTG_FS Receive status debug read(Host |
| FS_GRXFSIZ | `0x0024` | OTG_FS Receive FIFO size register |
| FS_GNPTXFSIZ_Device | `0x0028` | OTG_FS non-periodic transmit FIFO size |
| FS_GNPTXFSIZ_Host | `0x0028` | OTG_FS non-periodic transmit FIFO size |
| FS_GNPTXSTS | `0x002c` | OTG_FS non-periodic transmit FIFO/queue |
| FS_GCCFG | `0x0038` | OTG_FS general core configuration register |
| FS_CID | `0x003c` | core ID register |
| FS_HPTXFSIZ | `0x0100` | OTG_FS Host periodic transmit FIFO size |
| FS_DIEPTXF1 | `0x0104` | OTG_FS device IN endpoint transmit FIFO size |
| FS_DIEPTXF2 | `0x0108` | OTG_FS device IN endpoint transmit FIFO size |
| FS_DIEPTXF3 | `0x010c` | OTG_FS device IN endpoint transmit FIFO size |

## OTG_FS_HOST — `0x50000400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| FS_HCFG | `0x0000` | OTG_FS host configuration register |
| HFIR | `0x0004` | OTG_FS Host frame interval |
| FS_HFNUM | `0x0008` | OTG_FS host frame number/frame time |
| FS_HPTXSTS | `0x0010` | OTG_FS_Host periodic transmit FIFO/queue |
| HAINT | `0x0014` | OTG_FS Host all channels interrupt |
| HAINTMSK | `0x0018` | OTG_FS host all channels interrupt mask |
| FS_HPRT | `0x0040` | OTG_FS host port control and status register |
| FS_HCCHAR0 | `0x0100` | OTG_FS host channel-0 characteristics |
| FS_HCINT0 | `0x0108` | OTG_FS host channel-0 interrupt register |
| FS_HCINTMSK0 | `0x010c` | OTG_FS host channel-0 mask register |
| FS_HCTSIZ0 | `0x0110` | OTG_FS host channel-0 transfer size |
| FS_HCCHAR1 | `0x0120` | OTG_FS host channel-1 characteristics |
| FS_HCINT1 | `0x0128` | OTG_FS host channel-1 interrupt register |
| FS_HCINTMSK1 | `0x012c` | OTG_FS host channel-1 mask register |
| FS_HCTSIZ1 | `0x0130` | OTG_FS host channel-1 transfer size |
| FS_HCCHAR2 | `0x0140` | OTG_FS host channel-2 characteristics |
| FS_HCINT2 | `0x0148` | OTG_FS host channel-2 interrupt register |
| FS_HCINTMSK2 | `0x014c` | OTG_FS host channel-2 mask register |
| FS_HCTSIZ2 | `0x0150` | OTG_FS host channel-2 transfer size |
| FS_HCCHAR3 | `0x0160` | OTG_FS host channel-3 characteristics |
| FS_HCINT3 | `0x0168` | OTG_FS host channel-3 interrupt register |
| FS_HCINTMSK3 | `0x016c` | OTG_FS host channel-3 mask register |
| FS_HCTSIZ3 | `0x0170` | OTG_FS host channel-3 transfer size |
| FS_HCCHAR4 | `0x0180` | OTG_FS host channel-4 characteristics |
| FS_HCINT4 | `0x0188` | OTG_FS host channel-4 interrupt register |
| FS_HCINTMSK4 | `0x018c` | OTG_FS host channel-4 mask register |
| FS_HCTSIZ4 | `0x0190` | OTG_FS host channel-x transfer size |
| FS_HCCHAR5 | `0x01a0` | OTG_FS host channel-5 characteristics |
| FS_HCINT5 | `0x01a8` | OTG_FS host channel-5 interrupt register |
| FS_HCINTMSK5 | `0x01ac` | OTG_FS host channel-5 mask register |
| FS_HCTSIZ5 | `0x01b0` | OTG_FS host channel-5 transfer size |
| FS_HCCHAR6 | `0x01c0` | OTG_FS host channel-6 characteristics |
| FS_HCINT6 | `0x01c8` | OTG_FS host channel-6 interrupt register |
| FS_HCINTMSK6 | `0x01cc` | OTG_FS host channel-6 mask register |
| FS_HCTSIZ6 | `0x01d0` | OTG_FS host channel-6 transfer size |
| FS_HCCHAR7 | `0x01e0` | OTG_FS host channel-7 characteristics |
| FS_HCINT7 | `0x01e8` | OTG_FS host channel-7 interrupt register |
| FS_HCINTMSK7 | `0x01ec` | OTG_FS host channel-7 mask register |
| FS_HCTSIZ7 | `0x01f0` | OTG_FS host channel-7 transfer size |

## OTG_FS_PWRCLK — `0x50000e00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| FS_PCGCCTL | `0x0000` | OTG_FS power and clock gating control |

## PWR — `0x40007000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR | `0x0000` | Power control register |
| CSR | `0x0004` | Power control register |

## RCC — `0x40021000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR | `0x0000` | Clock control register |
| CFGR | `0x0004` | Clock configuration register |
| CIR | `0x0008` | Clock interrupt register |
| APB2RSTR | `0x000c` | APB2 peripheral reset register |
| APB1RSTR | `0x0010` | APB1 peripheral reset register |
| AHBENR | `0x0014` | AHB Peripheral Clock enable register |
| APB2ENR | `0x0018` | APB2 peripheral clock enable register |
| APB1ENR | `0x001c` | APB1 peripheral clock enable register |
| BDCR | `0x0020` | Backup domain control register |
| CSR | `0x0024` | Control/status register |

## RTC — `0x40002800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CRH | `0x0000` | RTC Control Register High |
| CRL | `0x0004` | RTC Control Register Low |
| PRLH | `0x0008` | RTC Prescaler Load Register |
| PRLL | `0x000c` | RTC Prescaler Load Register |
| DIVH | `0x0010` | RTC Prescaler Divider Register |
| DIVL | `0x0014` | RTC Prescaler Divider Register |
| CNTH | `0x0018` | RTC Counter Register High |
| CNTL | `0x001c` | RTC Counter Register Low |
| ALRH | `0x0020` | RTC Alarm Register High |
| ALRL | `0x0024` | RTC Alarm Register Low |

## SCB — `0xe000ed00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CPUID | `0x0000` | CPUID base register |
| ICSR | `0x0004` | Interrupt control and state |
| VTOR | `0x0008` | Vector table offset register |
| AIRCR | `0x000c` | Application interrupt and reset control |
| SCR | `0x0010` | System control register |
| CCR | `0x0014` | Configuration and control |
| SHPR1 | `0x0018` | System handler priority |
| SHPR2 | `0x001c` | System handler priority |
| SHPR3 | `0x0020` | System handler priority |
| SHCRS | `0x0024` | System handler control and state |
| CFSR_UFSR_BFSR_MMFSR | `0x0028` | Configurable fault status |
| HFSR | `0x002c` | Hard fault status register |
| MMFAR | `0x0034` | Memory management fault address |
| BFAR | `0x0038` | Bus fault address register |

## SCB_ACTRL — `0xe000e008`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| ACTRL | `0x0000` | Auxiliary control register |

## SDIO — `0x40018000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| POWER | `0x0000` | Bits 1:0 = PWRCTRL: Power supply control |
| CLKCR | `0x0004` | SDI clock control register |
| ARG | `0x0008` | Bits 31:0 = : Command argument |
| CMD | `0x000c` | SDIO command register |
| RESPCMD | `0x0010` | SDIO command register |
| RESPI1 | `0x0014` | Bits 31:0 = CARDSTATUS1 |
| RESP2 | `0x0018` | Bits 31:0 = CARDSTATUS2 |
| RESP3 | `0x001c` | Bits 31:0 = CARDSTATUS3 |
| RESP4 | `0x0020` | Bits 31:0 = CARDSTATUS4 |
| DTIMER | `0x0024` | Bits 31:0 = DATATIME: Data timeout |
| DLEN | `0x0028` | Bits 24:0 = DATALENGTH: Data length |
| DCTRL | `0x002c` | SDIO data control register |
| DCOUNT | `0x0030` | Bits 24:0 = DATACOUNT: Data count |
| STA | `0x0034` | SDIO status register |
| ICR | `0x0038` | SDIO interrupt clear register |
| MASK | `0x003c` | SDIO mask register (SDIO_MASK) |
| FIFOCNT | `0x0048` | Bits 23:0 = FIFOCOUNT: Remaining number of |
| FIFO | `0x0080` | bits 31:0 = FIFOData: Receive and transmit |

## SPI1 — `0x40013000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR1 | `0x0000` | control register 1 |
| CR2 | `0x0004` | control register 2 |
| SR | `0x0008` | status register |
| DR | `0x000c` | data register |
| CRCPR | `0x0010` | CRC polynomial register |
| RXCRCR | `0x0014` | RX CRC register |
| TXCRCR | `0x0018` | TX CRC register |
| I2SCFGR | `0x001c` | I2S configuration register |
| I2SPR | `0x0020` | I2S prescaler register |

## SPI2 — `0x40003800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## SPI3 — `0x40003c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## STK — `0xe000e010`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CTRL | `0x0000` | SysTick control and status |
| LOAD_ | `0x0004` | SysTick reload value register |
| VAL | `0x0008` | SysTick current value register |
| CALIB | `0x000c` | SysTick calibration value |

## TIM1 — `0x40012c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR1 | `0x0000` | control register 1 |
| CR2 | `0x0004` | control register 2 |
| SMCR | `0x0008` | slave mode control register |
| DIER | `0x000c` | DMA/Interrupt enable register |
| SR | `0x0010` | status register |
| EGR | `0x0014` | event generation register |
| CCMR1_Output | `0x0018` | capture/compare mode register (output |
| CCMR1_Input | `0x0018` | capture/compare mode register 1 (input |
| CCMR2_Output | `0x001c` | capture/compare mode register (output |
| CCMR2_Input | `0x001c` | capture/compare mode register 2 (input |
| CCER | `0x0020` | capture/compare enable |
| CNT | `0x0024` | counter |
| PSC | `0x0028` | prescaler |
| ARR | `0x002c` | auto-reload register |
| RCR | `0x0030` | repetition counter register |
| CCR1 | `0x0034` | capture/compare register 1 |
| CCR2 | `0x0038` | capture/compare register 2 |
| CCR3 | `0x003c` | capture/compare register 3 |
| CCR4 | `0x0040` | capture/compare register 4 |
| BDTR | `0x0044` | break and dead-time register |
| DCR | `0x0048` | DMA control register |
| DMAR | `0x004c` | DMA address for full transfer |

## TIM10 — `0x40015000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR1 | `0x0000` | control register 1 |
| CR2 | `0x0004` | control register 2 |
| DIER | `0x000c` | DMA/Interrupt enable register |
| SR | `0x0010` | status register |
| EGR | `0x0014` | event generation register |
| CCMR1_Output | `0x0018` | capture/compare mode register (output |
| CCMR1_Input | `0x0018` | capture/compare mode register (input |
| CCER | `0x0020` | capture/compare enable |
| CNT | `0x0024` | counter |
| PSC | `0x0028` | prescaler |
| ARR | `0x002c` | auto-reload register |
| CCR1 | `0x0034` | capture/compare register 1 |

## TIM11 — `0x40015400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM12 — `0x40001800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM13 — `0x40001c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM14 — `0x40002000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM2 — `0x40000000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR1 | `0x0000` | control register 1 |
| CR2 | `0x0004` | control register 2 |
| SMCR | `0x0008` | slave mode control register |
| DIER | `0x000c` | DMA/Interrupt enable register |
| SR | `0x0010` | status register |
| EGR | `0x0014` | event generation register |
| CCMR1_Output | `0x0018` | capture/compare mode register 1 (output |
| CCMR1_Input | `0x0018` | capture/compare mode register 1 (input |
| CCMR2_Output | `0x001c` | capture/compare mode register 2 (output |
| CCMR2_Input | `0x001c` | capture/compare mode register 2 (input |
| CCER | `0x0020` | capture/compare enable |
| CNT | `0x0024` | counter |
| PSC | `0x0028` | prescaler |
| ARR | `0x002c` | auto-reload register |
| CCR1 | `0x0034` | capture/compare register 1 |
| CCR2 | `0x0038` | capture/compare register 2 |
| CCR3 | `0x003c` | capture/compare register 3 |
| CCR4 | `0x0040` | capture/compare register 4 |
| DCR | `0x0048` | DMA control register |
| DMAR | `0x004c` | DMA address for full transfer |

## TIM3 — `0x40000400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM4 — `0x40000800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM5 — `0x40000c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM6 — `0x40001000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR1 | `0x0000` | control register 1 |
| CR2 | `0x0004` | control register 2 |
| DIER | `0x000c` | DMA/Interrupt enable register |
| SR | `0x0010` | status register |
| EGR | `0x0014` | event generation register |
| CNT | `0x0024` | counter |
| PSC | `0x0028` | prescaler |
| ARR | `0x002c` | auto-reload register |

## TIM7 — `0x40001400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM8 — `0x40013400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## TIM9 — `0x40014c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR1 | `0x0000` | control register 1 |
| CR2 | `0x0004` | control register 2 |
| SMCR | `0x0008` | slave mode control register |
| DIER | `0x000c` | DMA/Interrupt enable register |
| SR | `0x0010` | status register |
| EGR | `0x0014` | event generation register |
| CCMR1_Output | `0x0018` | capture/compare mode register 1 (output |
| CCMR1_Input | `0x0018` | capture/compare mode register 1 (input |
| CCER | `0x0020` | capture/compare enable |
| CNT | `0x0024` | counter |
| PSC | `0x0028` | prescaler |
| ARR | `0x002c` | auto-reload register |
| CCR1 | `0x0034` | capture/compare register 1 |
| CCR2 | `0x0038` | capture/compare register 2 |

## UART4 — `0x40004c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| SR | `0x0000` | UART4_SR |
| DR | `0x0004` | UART4_DR |
| BRR | `0x0008` | UART4_BRR |
| CR1 | `0x000c` | UART4_CR1 |
| CR2 | `0x0010` | UART4_CR2 |
| CR3 | `0x0014` | UART4_CR3 |

## UART5 — `0x40005000`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| SR | `0x0000` | UART4_SR |
| DR | `0x0004` | UART4_DR |
| BRR | `0x0008` | UART4_BRR |
| CR1 | `0x000c` | UART4_CR1 |
| CR2 | `0x0010` | UART4_CR2 |
| CR3 | `0x0014` | UART4_CR3 |

## USART1 — `0x40013800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| SR | `0x0000` | Status register |
| DR | `0x0004` | Data register |
| BRR | `0x0008` | Baud rate register |
| CR1 | `0x000c` | Control register 1 |
| CR2 | `0x0010` | Control register 2 |
| CR3 | `0x0014` | Control register 3 |
| GTPR | `0x0018` | Guard time and prescaler |

## USART2 — `0x40004400`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## USART3 — `0x40004800`

| 寄存器 | 偏移 | 说明 |
|---|---|---|

## USB — `0x40005c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| EP0R | `0x0000` | endpoint 0 register |
| EP1R | `0x0004` | endpoint 1 register |
| EP2R | `0x0008` | endpoint 2 register |
| EP3R | `0x000c` | endpoint 3 register |
| EP4R | `0x0010` | endpoint 4 register |
| EP5R | `0x0014` | endpoint 5 register |
| EP6R | `0x0018` | endpoint 6 register |
| EP7R | `0x001c` | endpoint 7 register |
| CNTR | `0x0040` | control register |
| ISTR | `0x0044` | interrupt status register |
| FNR | `0x0048` | frame number register |
| DADDR | `0x004c` | device address |
| BTABLE | `0x0050` | Buffer table address |

## WWDG — `0x40002c00`

| 寄存器 | 偏移 | 说明 |
|---|---|---|
| CR | `0x0000` | Control register (WWDG_CR) |
| CFR | `0x0004` | Configuration register |
| SR | `0x0008` | Status register (WWDG_SR) |

