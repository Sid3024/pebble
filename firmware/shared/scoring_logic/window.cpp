#include "window.h"
#include "accel.h"
#include <math.h>

// FreeRTOS headers differ between ESP32 and nRF52 Arduino frameworks.
#ifdef ARDUINO_ARCH_ESP32
  #include "freertos/FreeRTOS.h"
  #include "freertos/task.h"
  #include "freertos/semphr.h"
#else
  // nRF52 (Adafruit/Seeed Arduino core) exposes FreeRTOS at top-level paths.
  #include <FreeRTOS.h>
  #include <task.h>
  #include <semphr.h>
#endif

static float             s_buf[WINDOW_BUFFER_SIZE];
static volatile uint32_t s_head  = 0;
static volatile uint32_t s_count = 0;
static SemaphoreHandle_t s_mutex = nullptr;

static void sampling_task(void *) {
    const TickType_t period = pdMS_TO_TICKS(1000 / SAMPLE_RATE_HZ);
    TickType_t       wake   = xTaskGetTickCount();

    float    sum   = 0.0f;
    uint32_t n     = 0;

    for (;;) {
        vTaskDelayUntil(&wake, period);

        float ax, ay, az;
        if (!accel_read(ax, ay, az)) continue;

        sum += sqrtf(ax * ax + ay * ay + az * az);
        n++;

        if (n >= SAMPLES_PER_WINDOW) {
            xSemaphoreTake(s_mutex, portMAX_DELAY);
            s_buf[s_head] = sum;
            s_head = (s_head + 1) % WINDOW_BUFFER_SIZE;
            if (s_count < WINDOW_BUFFER_SIZE) s_count++;
            xSemaphoreGive(s_mutex);

            sum = 0.0f;
            n   = 0;
        }
    }
}

void window_task_start() {
    s_mutex = xSemaphoreCreateMutex();
    xTaskCreate(sampling_task, "accel_win", 4096, nullptr, 5, nullptr);
}

uint32_t window_available() {
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    uint32_t c = s_count;
    xSemaphoreGive(s_mutex);
    return c;
}

bool window_pop(float &out) {
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    if (s_count == 0) { xSemaphoreGive(s_mutex); return false; }
    uint32_t tail = (s_head + WINDOW_BUFFER_SIZE - s_count) % WINDOW_BUFFER_SIZE;
    out = s_buf[tail];
    s_count--;
    xSemaphoreGive(s_mutex);
    return true;
}
