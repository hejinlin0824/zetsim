/* HAL configuration for the led_marquee teaching project. */
#ifndef STM32F1XX_HAL_CONF_H
#define STM32F1XX_HAL_CONF_H

#define HAL_MODULE_ENABLED
#define HAL_CORTEX_MODULE_ENABLED
#define HAL_FLASH_MODULE_ENABLED
#define HAL_GPIO_MODULE_ENABLED
#define HAL_RCC_MODULE_ENABLED

#define HSE_VALUE              8000000U
#define HSE_STARTUP_TIMEOUT    100U
#define HSI_VALUE              8000000U
#define LSI_VALUE              40000U
#define LSE_VALUE              32768U
#define LSE_STARTUP_TIMEOUT    5000U
#define VDD_VALUE              3300U
#define TICK_INT_PRIORITY      0x0FU
#define USE_RTOS               0U
#define PREFETCH_ENABLE        1U

#define USE_HAL_ADC_REGISTER_CALLBACKS         0U
#define USE_HAL_CAN_REGISTER_CALLBACKS          0U
#define USE_HAL_CEC_REGISTER_CALLBACKS          0U
#define USE_HAL_DAC_REGISTER_CALLBACKS          0U
#define USE_HAL_ETH_REGISTER_CALLBACKS          0U
#define USE_HAL_HCD_REGISTER_CALLBACKS          0U
#define USE_HAL_I2C_REGISTER_CALLBACKS          0U
#define USE_HAL_I2S_REGISTER_CALLBACKS          0U
#define USE_HAL_MMC_REGISTER_CALLBACKS          0U
#define USE_HAL_NAND_REGISTER_CALLBACKS         0U
#define USE_HAL_NOR_REGISTER_CALLBACKS          0U
#define USE_HAL_PCD_REGISTER_CALLBACKS          0U
#define USE_HAL_RTC_REGISTER_CALLBACKS          0U
#define USE_HAL_SD_REGISTER_CALLBACKS           0U
#define USE_HAL_SPI_REGISTER_CALLBACKS          0U
#define USE_HAL_TIM_REGISTER_CALLBACKS          0U
#define USE_HAL_UART_REGISTER_CALLBACKS         0U
#define USE_HAL_USART_REGISTER_CALLBACKS        0U
#define USE_HAL_WWDG_REGISTER_CALLBACKS         0U

#ifdef HAL_RCC_MODULE_ENABLED
#include "stm32f1xx_hal_rcc.h"
#endif
#ifdef HAL_GPIO_MODULE_ENABLED
#include "stm32f1xx_hal_gpio.h"
#endif
#ifdef HAL_CORTEX_MODULE_ENABLED
#include "stm32f1xx_hal_cortex.h"
#endif
#ifdef HAL_FLASH_MODULE_ENABLED
#include "stm32f1xx_hal_flash.h"
#endif



/* Match the official template default: parameter assertions are disabled
 * unless USE_FULL_ASSERT is explicitly enabled by the application.
 */
#ifndef USE_FULL_ASSERT
#ifndef assert_param
#define assert_param(expr) ((void)0U)
#endif
#else
#ifndef assert_param
void assert_failed(uint8_t *file, uint32_t line);
#define assert_param(expr) ((expr) ? (void)0U : assert_failed((uint8_t *)__FILE__, __LINE__))
#endif
#endif

#endif
