#include "vibration.h"
#include "config/board_config.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static TaskHandle_t s_task = nullptr;

// ── LEDC helpers ──────────────────────────────────────────────

static inline void motor_on(uint8_t duty, uint32_t ms) {
    ledcWrite(VIBRATION_LEDC_CHANNEL, duty);
    vTaskDelay(pdMS_TO_TICKS(ms));
}
static inline void motor_off(uint32_t ms) {
    ledcWrite(VIBRATION_LEDC_CHANNEL, 0);
    if (ms) vTaskDelay(pdMS_TO_TICKS(ms));
}
static inline void pulse(uint8_t duty, uint32_t on_ms, uint32_t off_ms) {
    motor_on(duty, on_ms);
    motor_off(off_ms);
}

// ── Pattern task ──────────────────────────────────────────────

static void vibration_task(void* pv) {
    uint8_t id = (uint8_t)(uintptr_t)pv;

    switch (id) {
        case VIBR_TEAM1: {
            TickType_t start = xTaskGetTickCount();
            while (xTaskGetTickCount() - start < pdMS_TO_TICKS(5000)) {
                pulse(VIBRATION_DUTY_FULL, 150, 80);
                pulse(VIBRATION_DUTY_FULL, 150, 80);
                pulse(VIBRATION_DUTY_FULL, 150, 500);
            }
            break;
        }
        case VIBR_TEAM2: {
            TickType_t start = xTaskGetTickCount();
            while (xTaskGetTickCount() - start < pdMS_TO_TICKS(5000)) {
                pulse(VIBRATION_DUTY_FULL, 500, 150);
                pulse(VIBRATION_DUTY_FULL, 200, 650);
            }
            break;
        }
        case VIBR_MILESTONE1:
            pulse(VIBRATION_DUTY_SOFT, 150, 100);
            pulse(VIBRATION_DUTY_SOFT, 150, 0);
            break;
        case VIBR_MILESTONE2:
            pulse(VIBRATION_DUTY_SOFT, 250, 150);
            pulse(VIBRATION_DUTY_SOFT, 250, 150);
            pulse(VIBRATION_DUTY_SOFT, 250, 0);
            break;
        case VIBR_MILESTONE3:
            pulse(VIBRATION_DUTY_FULL, 200, 100);
            pulse(VIBRATION_DUTY_FULL, 200, 100);
            pulse(VIBRATION_DUTY_FULL, 200, 100);
            pulse(VIBRATION_DUTY_FULL, 200, 0);
            break;
        case VIBR_WIN:
            pulse(VIBRATION_DUTY_FULL, 80, 60);
            pulse(VIBRATION_DUTY_FULL, 80, 60);
            pulse(VIBRATION_DUTY_FULL, 80, 60);
            pulse(VIBRATION_DUTY_FULL, 80, 60);
            pulse(VIBRATION_DUTY_FULL, 80, 200);
            motor_on(VIBRATION_DUTY_FULL, 600);
            break;
        case VIBR_FLOWER_50:
            pulse(VIBRATION_DUTY_FULL, 100, 80);
            pulse(VIBRATION_DUTY_FULL, 100, 80);
            motor_on(VIBRATION_DUTY_FULL, 350);
            break;
    }

    motor_off(0);
    s_task = nullptr;
    vTaskDelete(nullptr);
}

// ── Public API ────────────────────────────────────────────────

void vibration_init() {
    ledcSetup(VIBRATION_LEDC_CHANNEL, VIBRATION_LEDC_FREQ, VIBRATION_LEDC_RES);
    ledcAttachPin(VIBRATION_PIN, VIBRATION_LEDC_CHANNEL);
    ledcWrite(VIBRATION_LEDC_CHANNEL, 0);
}

void vibration_play(uint8_t pattern_id) {
    if (s_task != nullptr) {
        vTaskDelete(s_task);
        s_task = nullptr;
        ledcWrite(VIBRATION_LEDC_CHANNEL, 0);
    }
    Serial.printf("[VIBR] pattern %d\n", pattern_id);
    xTaskCreate(vibration_task, "vibr", 2048,
                (void*)(uintptr_t)pattern_id, 3, &s_task);
}
