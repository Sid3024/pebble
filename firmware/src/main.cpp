/*
 * main.cpp — Pebble Pod Firmware Entry Point (XIAO ESP32S3)
 *
 * Orchestrates the entire sensor pod: I2C bus recovery, MPU6050 init,
 * vibration motor, BLE server. Main loop drains IMU windows from the
 * FreeRTOS sampling task and sends them as 20-byte BLE notifications.
 *
 * Data flow:  MPU6050 -> sampling_task (100Hz) -> ring buffer -> loop()
 *             -> ble_send_window() -> BLE notification -> Python host
 *
 * Recovery: i2c_bus_recover() pulses SCL 9 times if SDA is stuck LOW.
 *           Wire.setTimeOut(50) prevents 1s blocks that kill USB-CDC.
 *           Retry every 2s if IMU init fails (try_hw_init).
 */

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

// Pulse SCL 9 times to free any device holding SDA LOW from an incomplete
// transaction (standard I2C bus recovery). Must be called before Wire.begin().
static void i2c_bus_recover() {
#if !USE_EXPANSION_BOARD
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, OUTPUT);
    for (int i = 0; i < 9; i++) {
        digitalWrite(I2C_SCL, HIGH); delayMicroseconds(5);
        if (digitalRead(I2C_SDA)) break;  // SDA released — bus is free
        digitalWrite(I2C_SCL, LOW);  delayMicroseconds(5);
    }
    // Generate STOP condition to complete any lingering transaction
    pinMode(I2C_SDA, OUTPUT);
    digitalWrite(I2C_SDA, LOW);  delayMicroseconds(5);
    digitalWrite(I2C_SCL, HIGH); delayMicroseconds(5);
    digitalWrite(I2C_SDA, HIGH); delayMicroseconds(5);
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, INPUT_PULLUP);
    Serial.println("[I2C] bus recovery pulses sent");
#endif
}

static void try_hw_init() {
    vibration_init();
#if !USE_EXPANSION_BOARD
    i2c_bus_recover();
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setTimeOut(50);  // 50 ms max per transaction — prevents 1s hangs
#endif

    if (!imu_init()) {
        Serial.println("[ERROR] MPU6050 not found - running diagnostic...");
        imu_diagnose();
        s_next_retry_ms = millis() + 5000;
        return;
    }

    window_task_start();
    s_hw_ready = true;
    Serial.printf("[INFO] IMU ready. Sampling at %d Hz, window = %.2f s (%d samples)\n",
                  SAMPLE_RATE_HZ, WINDOW_DURATION_S, SAMPLES_PER_WINDOW);
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) delay(10);

#if USE_EXPANSION_BOARD
    Wire.begin();
    Wire.setTimeOut(50);
    Serial.println("[INFO] I2C: expansion board (default pins)");
#else
    pinMode(IMU_INT_PIN, INPUT);
    Serial.printf("[INFO] I2C: direct wiring SDA=D%d SCL=D%d INT1=D%d\n",
                  I2C_SDA, I2C_SCL, IMU_INT_PIN);
    // Wire.begin() + bus recovery handled in try_hw_init() so it also runs on
    // every retry (not just once at boot).
#endif

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
