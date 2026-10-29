/*
 * ESP32-S3 GPIO blink using official ESP-IDF APIs.
 *
 * This is a native ESP-IDF application: Xtensa LX7 code is built by the
 * Espressif toolchain and run by Espressif's ESP32-S3-capable QEMU, never by
 * the STM32 Cortex-M3/Unicorn backend.
 *
 * Example wiring on a suitable development board:
 *   GPIO2 -> 330-ohm resistor -> LED anode; LED cathode -> GND.
 * GPIO2 is only an example pin; check the exact board/module schematic.
 */
#include <stdio.h>

#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define BLINK_GPIO GPIO_NUM_2
#define BLINK_PERIOD_MS 500

static const char *TAG = "zetsim-esp32s3";

void app_main(void)
{
    /*
     * Keep a marker before touching GPIO. If QEMU panics below, CI can prove
     * that app_main was entered and narrow the failure to peripheral setup.
     */
    printf("ZETSIM_ESP32S3_APP_MAIN_ENTERED\n");
    fflush(stdout);

    const gpio_config_t config = {
        .pin_bit_mask = 1ULL << BLINK_GPIO,
        /* gpio_get_level() reads the input path, so enable input as well as output. */
        .mode = GPIO_MODE_INPUT_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&config));

    printf("ZETSIM_ESP32S3_GPIO_CONFIG_OK\n");
    fflush(stdout);
    ESP_LOGI(TAG, "ZETSIM_ESP32S3_BOOT_OK: ESP-IDF app_main and GPIO setup completed");

    int level = 0;
    while (1) {
        level = !level;
        ESP_ERROR_CHECK(gpio_set_level(BLINK_GPIO, level));
        const int readback = gpio_get_level(BLINK_GPIO);
        printf("ZETSIM_ESP32S3_GPIO2=%d\n", level);
        printf("ZETSIM_ESP32S3_GPIO2_READBACK=%d\n", readback);
        if (readback != level) {
            printf("ZETSIM_ESP32S3_GPIO2_READBACK_MISMATCH expected=%d got=%d\n", level, readback);
        }
        fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(BLINK_PERIOD_MS));
    }
}
