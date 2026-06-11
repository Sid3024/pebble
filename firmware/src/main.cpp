#include <Arduino.h>
#include <Wire.h>
#include "config/board_config.h"
#include "accel/accel.h"
#include "window/window.h"
#include "ble/ble.h"
#include "vibration/vibration.h"

static bool     s_hw_ready           = false;
static uint32_t s_next_retry_ms      = 0;
static uint32_t s_last_status_send_ms = 0;

static void try_hw_init() {
    vibration_init();

    if (!imu_init()) {
        Serial.println("[ERROR] MPU6050 not found - running diagnostic...");
        imu_diagnose();
        s_next_retry_ms = millis() + 5000;
        return;
    }

    window_task_start();
    s_hw_ready = true;
    Serial.printf("[INFO] IMU ready. Sampling at %d Hz, window = %d s (%d samples)\n",
                  SAMPLE_RATE_HZ, WINDOW_DURATION_S, SAMPLES_PER_WINDOW);
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) delay(10);

#if USE_EXPANSION_BOARD
    Wire.begin();
    Serial.println("[INFO] I2C: expansion board (default pins)");
#else
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, INPUT_PULLUP);
    pinMode(IMU_INT_PIN, INPUT);
    Wire.begin(I2C_SDA, I2C_SCL);
    Serial.printf("[INFO] I2C: direct wiring SDA=D%d SCL=D%d INT1=D%d\n",
                  I2C_SDA, I2C_SCL, IMU_INT_PIN);
#endif

    // Scan I2C bus and print found addresses — helps diagnose address mismatches.
    Serial.print("[I2C] scanning... ");
    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0)
            Serial.printf("0x%02X ", addr);
    }
    Serial.println();

    ble_set_command_callback([](uint8_t id) { vibration_play(id); });
    ble_init();

    try_hw_init();
}

void loop() {
    if (!s_hw_ready) {
        if (millis() >= s_next_retry_ms)
            try_hw_init();
        // Notify connected Python hub that the IMU is offline every 3 s.
        if (ble_connected() && millis() - s_last_status_send_ms > 3000) {
            ble_send_status(0x01);
            s_last_status_send_ms = millis();
        }
        delay(100);
        return;
    }

    ImuWindow window;
    while (window_pop(window)) {
        Serial.printf("[WINDOW] imu samples=%u connected=%d\n", window.samples, ble_connected());
        ble_send_window(window);
    }
    delay(100);
}
