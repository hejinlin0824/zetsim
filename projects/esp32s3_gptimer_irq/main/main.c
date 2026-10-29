/*
 * ESP32-S3 GPTimer alarm interrupt regression for zetsim.
 *
 * This uses the official ESP-IDF GPTimer driver. The alarm callback must run
 * in interrupt context; the task reports the observed callback count on UART0.
 */
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "driver/gptimer.h"
#include "esp_attr.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define ZETSIM_GPTIMER_RESOLUTION_HZ 1000000
#define ZETSIM_GPTIMER_ALARM_TICKS 10000
#define ZETSIM_GPTIMER_RUN_MS 260
#define ZETSIM_GPTIMER_MIN_IRQS 5

static volatile uint32_t g_alarm_count;

static bool IRAM_ATTR zetsim_gptimer_on_alarm(
    gptimer_handle_t timer,
    const gptimer_alarm_event_data_t *event_data,
    void *user_data)
{
    (void)timer;
    (void)event_data;
    (void)user_data;
    g_alarm_count++;
    return false;
}

void app_main(void)
{
    printf("ZETSIM_GPTIMER_IRQ_APP_MAIN_ENTERED\n");
    fflush(stdout);

    gptimer_handle_t timer = NULL;
    const gptimer_config_t timer_config = {
        .clk_src = GPTIMER_CLK_SRC_DEFAULT,
        .direction = GPTIMER_COUNT_UP,
        .resolution_hz = ZETSIM_GPTIMER_RESOLUTION_HZ,
    };
    ESP_ERROR_CHECK(gptimer_new_timer(&timer_config, &timer));

    const gptimer_event_callbacks_t callbacks = {
        .on_alarm = zetsim_gptimer_on_alarm,
    };
    ESP_ERROR_CHECK(gptimer_register_event_callbacks(timer, &callbacks, NULL));
    ESP_ERROR_CHECK(gptimer_enable(timer));

    const gptimer_alarm_config_t alarm_config = {
        .reload_count = 0,
        .alarm_count = ZETSIM_GPTIMER_ALARM_TICKS,
        .flags.auto_reload_on_alarm = true,
    };
    ESP_ERROR_CHECK(gptimer_set_alarm_action(timer, &alarm_config));
    ESP_ERROR_CHECK(gptimer_start(timer));
    printf("ZETSIM_GPTIMER_IRQ_STARTED period_us=%d\n", ZETSIM_GPTIMER_ALARM_TICKS);
    fflush(stdout);

    vTaskDelay(pdMS_TO_TICKS(ZETSIM_GPTIMER_RUN_MS));
    ESP_ERROR_CHECK(gptimer_stop(timer));
    const uint32_t count = g_alarm_count;
    printf("ZETSIM_GPTIMER_IRQ_COUNT=%" PRIu32 "\n", count);
    fflush(stdout);

    ESP_ERROR_CHECK(gptimer_disable(timer));
    ESP_ERROR_CHECK(gptimer_del_timer(timer));

    if (count >= ZETSIM_GPTIMER_MIN_IRQS) {
        printf("ZETSIM_GPTIMER_IRQ_PASS count=%" PRIu32 "\n", count);
    } else {
        printf("ZETSIM_GPTIMER_IRQ_FAIL count=%" PRIu32 " expected_at_least=%d\n",
               count, ZETSIM_GPTIMER_MIN_IRQS);
    }
    fflush(stdout);
}
