#include <Arduino.h>
#include <Wire.h>
#include "config/board_config.h"
#include "ble/ble.h"
#include "vibration/vibration.h"
// Shared libs (from ../shared via lib_extra_dirs)
#include <accel.h>
#include <window.h>

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) delay(10);

    // nRF52840 Wire defaults to D4/D5 regardless of expansion board or direct wiring.
    Wire.begin();
    Serial.println("[INFO] I2C: Wire.begin() — D4=SDA, D5=SCL");

    if (!accel_init(ACCEL_I2C_ADDR)) {
        Serial.println("[ERROR] LIS3DHTR not found. Check wiring.");
        while (true) delay(1000);
    }

    vibration_init();
    ble_set_command_callback([](uint8_t id) { vibration_play(id); });
    ble_init();
    window_task_start();

    Serial.printf("[INFO] Sampling %d Hz, window %d s (%d samples)\n",
                  SAMPLE_RATE_HZ, WINDOW_DURATION_S, SAMPLES_PER_WINDOW);
}

void loop() {
    float sum;
    while (window_pop(sum)) {
        Serial.printf("[WINDOW] %.4f g  connected=%d\n", sum, ble_connected());
        ble_send_window(sum);
    }
    delay(100);
}
