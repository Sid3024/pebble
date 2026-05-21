#include "window.h"
#include "accel/accel.h"
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

// ── Ring buffer ────────────────────────────────────────────────────────────
static float            s_buf[WINDOW_BUFFER_SIZE];
static volatile uint32_t s_head  = 0;   // next write slot
static volatile uint32_t s_count = 0;   // number of valid entries
static SemaphoreHandle_t s_mutex = nullptr;

// ── Sampling task ──────────────────────────────────────────────────────────

static void sampling_task(void *) {
    // FreeRTOS tick rate on ESP32-Arduino defaults to 1000 Hz (1 ms/tick),
    // so pdMS_TO_TICKS(10) == 10 ticks — exact for 100 Hz.
    const TickType_t period_ticks = pdMS_TO_TICKS(1000 / SAMPLE_RATE_HZ);
    TickType_t       last_wake    = xTaskGetTickCount();

    float    window_sum   = 0.0f;
    uint32_t sample_count = 0;

    for (;;) {
        // Block until the next 10 ms boundary; compensates for any overrun.
        vTaskDelayUntil(&last_wake, period_ticks);

        float ax, ay, az;
        if (!accel_read(ax, ay, az)) continue;  // skip bad reads

        float mag = sqrtf(ax * ax + ay * ay + az * az);
        window_sum += mag;
        sample_count++;

        if (sample_count >= SAMPLES_PER_WINDOW) {
            // Commit the completed window to the ring buffer.
            xSemaphoreTake(s_mutex, portMAX_DELAY);
            s_buf[s_head] = window_sum;
            s_head = (s_head + 1) % WINDOW_BUFFER_SIZE;
            // When full, the oldest entry is silently overwritten.
            if (s_count < WINDOW_BUFFER_SIZE) s_count++;
            xSemaphoreGive(s_mutex);

            window_sum   = 0.0f;
            sample_count = 0;
        }
    }
}

// ── Public API ─────────────────────────────────────────────────────────────

void window_task_start() {
    s_mutex = xSemaphoreCreateMutex();
    // Priority 5: high enough not to be starved by loop(), low enough to
    // yield to WiFi/BT tasks if they are running.
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
    if (s_count == 0) {
        xSemaphoreGive(s_mutex);
        return false;
    }
    // Tail = oldest entry: head has already advanced past it.
    uint32_t tail = (s_head + WINDOW_BUFFER_SIZE - s_count) % WINDOW_BUFFER_SIZE;
    out = s_buf[tail];
    s_count--;
    xSemaphoreGive(s_mutex);
    return true;
}
