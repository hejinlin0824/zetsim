/*
 * zetsim ESP32-S3 UART1 echo regression. UART0 remains the diagnostic console.
 * UART1 is bridged to a host-side mock serial device by esp-emu's TCP server.
 */
#include <stdint.h>
#include <stdio.h>

#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define ZETSIM_UART_PORT UART_NUM_1
#define ZETSIM_UART_TX_GPIO GPIO_NUM_17
#define ZETSIM_UART_RX_GPIO GPIO_NUM_18
#define ZETSIM_UART_BAUD_RATE 115200
#define ZETSIM_UART_RX_BUFFER_SIZE 512
#define ZETSIM_UART_READ_BUFFER_SIZE 128

void app_main(void)
{
    printf("ZETSIM_UART1_ECHO_APP_MAIN_ENTERED\n");
    fflush(stdout);

    const uart_config_t uart_config = {
        .baud_rate = ZETSIM_UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    ESP_ERROR_CHECK(uart_driver_install(
        ZETSIM_UART_PORT, ZETSIM_UART_RX_BUFFER_SIZE, 0, 0, NULL, 0
    ));
    ESP_ERROR_CHECK(uart_param_config(ZETSIM_UART_PORT, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(
        ZETSIM_UART_PORT, ZETSIM_UART_TX_GPIO, ZETSIM_UART_RX_GPIO,
        UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE
    ));

    printf("ZETSIM_UART1_ECHO_READY baud=%d tx_gpio=%d rx_gpio=%d\n",
           ZETSIM_UART_BAUD_RATE, ZETSIM_UART_TX_GPIO, ZETSIM_UART_RX_GPIO);
    fflush(stdout);

    uint8_t buffer[ZETSIM_UART_READ_BUFFER_SIZE];
    for (;;) {
        const int received = uart_read_bytes(
            ZETSIM_UART_PORT, buffer, sizeof(buffer), pdMS_TO_TICKS(50)
        );
        if (received <= 0) {
            continue;
        }
        const int transmitted = uart_write_bytes(
            ZETSIM_UART_PORT, (const char *)buffer, (size_t)received
        );
        printf("ZETSIM_UART1_ECHO_RX_BYTES=%d TX_BYTES=%d\n", received, transmitted);
        fflush(stdout);
        if (transmitted != received) {
            printf("ZETSIM_UART1_ECHO_WRITE_MISMATCH rx=%d tx=%d\n", received, transmitted);
            fflush(stdout);
        }
    }
}
