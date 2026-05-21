#include <Arduino.h>
#include <Wire.h>
#include "accel/accel.h"
#include "window/window.h"
#include "ble/ble.h"

void setup() {
    Serial.begin(115200);
    // Wait up to 2s for USB CDC — skipped automatically on battery power.
    while (!Serial && millis() < 2000) delay(10);

    Wire.begin();

    if (!accel_init()) {
        Serial.println("[ERROR] LIS3DHTR not found. Check wiring and I2C address.");
        while (true) delay(1000);
    }

    ble_init();
    window_task_start();

    Serial.printf("[INFO] Sampling at %d Hz, window = %d s (%d samples)\n",
                  SAMPLE_RATE_HZ, WINDOW_DURATION_S, SAMPLES_PER_WINDOW);
}

void loop() {
    float sum;
    while (window_pop(sum)) {
        Serial.printf("[WINDOW] sum = %.4f g  connected=%d\n", sum, ble_connected());
        ble_send_window(sum);
    }
    delay(100);
}
