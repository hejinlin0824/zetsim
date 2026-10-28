/*
 * zetsim course-project compatibility wrapper.
 *
 * The peripheral register structures are NOT defined here. They come from the
 * unmodified STMicroelectronics CMSIS device header:
 *   third_party/cmsis-device-f1/Include/stm32f103xe.h
 *
 * STM32F103ZET6 belongs to the STM32F103xE device variant (high-density, 512-KB
 * Flash). The official CMSIS package selects it via STM32F103xE in stm32f1xx.h.
 * This short wrapper retains the historical include name used by course projects
 * while relying on the vendor's real register layout and address definitions.
 *
 * Official sources and licenses: third_party/README.md
 */
#ifndef ZETSIM_PROJECT_STM32F103_H
#define ZETSIM_PROJECT_STM32F103_H

#ifndef STM32F103xE
#define STM32F103xE
#endif

#include "stm32f1xx.h"

#endif /* ZETSIM_PROJECT_STM32F103_H */
