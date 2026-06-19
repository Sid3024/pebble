/*
 * window.cpp — FreeRTOS IMU Sampling Task and Ring Buffer
 *
 * Runs a dedicated FreeRTOS task (sampling_task) that reads the IMU at
 * exactly 100Hz using vTaskDelayUntil for jitter-free timing. Every 25
 * samples are averaged into one ImuWindow struct (250ms of data) and
 * pushed into a ring buffer. The main loop (in main.cpp) drains the
 * buffer and sends each window over BLE.
 *
 * Thread safety: only the sampling task writes to head; only the main
 * loop reads via window_pop(). The ring buffer is lock-free as long as
 * the consumer keeps up (128 slots = ~32s of headroom).
 */

#include "window.h"
#include "accel/accel.h"
#include <Wire.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

static ImuWindow        s_buf[WINDOW_BUFFER_SIZE];
static volatile uint32_t s_head  = 0;
static volatile uint32_t s_count = 0;
static SemaphoreHandle_t s_mutex = nullptr;

static float s_gravity_x = 0.0f;
static float s_gravity_y = 0.0f;
static float s_gravity_z = 0.0f;
static bool  s_gravity_ready = false;

static void push_window(const ImuWindow &window) {
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    s_buf[s_head] = window;
    s_head = (s_head + 1) % WINDOW_BUFFER_SIZE;
    if (s_count < WINDOW_BUFFER_SIZE) s_count++;
    xSemaphoreGive(s_mutex);
}

static void sampling_task(void *) {
    Serial.printf("[IMU] sampling task started (%d Hz, %d sample windows)\n",
                  SAMPLE_RATE_HZ, SAMPLES_PER_WINDOW);
    const TickType_t period_ticks = pdMS_TO_TICKS(1000 / SAMPLE_RATE_HZ);
    TickType_t       last_wake    = xTaskGetTickCount();

    ImuWindow accum{};
    uint32_t  consecutive_failures = 0;
    // Trigger diagnostic after 2 full windows worth of consecutive read failures
    constexpr uint32_t DIAG_THRESHOLD = 2 * SAMPLES_PER_WINDOW;

    for (;;) {
        vTaskDelayUntil(&last_wake, period_ticks);

        ImuSample sample;
        if (!imu_read(sample)) {
            consecutive_failures++;
            if (consecutive_failures == DIAG_THRESHOLD) {
                Serial.printf("[IMU] %u consecutive read failures — running diagnostic\n",
                              consecutive_failures);
                imu_diagnose();
                // Reset so diagnostic doesn't fire every window if still failing
                consecutive_failures = 0;
                accum = ImuWindow{};
            }
            continue;
        }
        consecutive_failures = 0;

        if (!s_gravity_ready) {
            s_gravity_x = sample.ax;
            s_gravity_y = sample.ay;
            s_gravity_z = sample.az;
            s_gravity_ready = true;
        }

        // Low-pass gravity estimate lets acceleration represent movement,
        // not just the static 1 g gravity vector.
        constexpr float gravity_alpha = 0.02f;
        s_gravity_x = (1.0f - gravity_alpha) * s_gravity_x + gravity_alpha * sample.ax;
        s_gravity_y = (1.0f - gravity_alpha) * s_gravity_y + gravity_alpha * sample.ay;
        s_gravity_z = (1.0f - gravity_alpha) * s_gravity_z + gravity_alpha * sample.az;

        const float move_x = sample.ax - s_gravity_x;
        const float move_y = sample.ay - s_gravity_y;
        const float move_z = sample.az - s_gravity_z;
        const float move_mag = sqrtf(move_x * move_x + move_y * move_y + move_z * move_z);
        const float gyro_mag = sqrtf(sample.gx * sample.gx + sample.gy * sample.gy + sample.gz * sample.gz);

        accum.samples++;
        accum.ax += move_x;
        accum.ay += move_y;
        accum.az += move_z;
        accum.gx += sample.gx;
        accum.gy += sample.gy;
        accum.gz += sample.gz;
        accum.roll += sample.roll;
        accum.pitch += sample.pitch;
        accum.activity += move_mag + 0.01f * gyro_mag;

        if (accum.samples == 1) {
            Serial.printf("[IMU] first sample: ax=%.3f ay=%.3f az=%.3f gx=%.1f gy=%.1f gz=%.1f roll=%.1f pitch=%.1f\n",
                          sample.ax, sample.ay, sample.az,
                          sample.gx, sample.gy, sample.gz,
                          sample.roll, sample.pitch);
        }

        if (accum.samples >= SAMPLES_PER_WINDOW) {
            const float inv = 1.0f / accum.samples;
            ImuWindow window = accum;
            window.ax *= inv;
            window.ay *= inv;
            window.az *= inv;
            window.gx *= inv;
            window.gy *= inv;
            window.gz *= inv;
            window.roll *= inv;
            window.pitch *= inv;
            window.activity *= inv;
            push_window(window);

            Serial.printf("[WINDOW] imu activity=%.3f move=%.3fg gyro=%.1fdps roll=%.1f pitch=%.1f\n",
                          window.activity,
                          sqrtf(window.ax * window.ax + window.ay * window.ay + window.az * window.az),
                          sqrtf(window.gx * window.gx + window.gy * window.gy + window.gz * window.gz),
                          window.roll, window.pitch);

            accum = ImuWindow{};
        }
    }
}

void window_task_start() {
    s_mutex = xSemaphoreCreateMutex();
    if (!s_mutex) {
        Serial.println("[IMU] failed to create window mutex");
        return;
    }
    BaseType_t ok = xTaskCreate(sampling_task, "imu_win", 8192, nullptr, 5, nullptr);
    if (ok != pdPASS) {
        Serial.println("[IMU] failed to start sampling task");
    }
}

uint32_t window_available() {
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    uint32_t c = s_count;
    xSemaphoreGive(s_mutex);
    return c;
}

bool window_pop(ImuWindow &out) {
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    if (s_count == 0) {
        xSemaphoreGive(s_mutex);
        return false;
    }
    uint32_t tail = (s_head + WINDOW_BUFFER_SIZE - s_count) % WINDOW_BUFFER_SIZE;
    out = s_buf[tail];
    s_count--;
    xSemaphoreGive(s_mutex);
    return true;
}
