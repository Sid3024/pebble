#include <Arduino.h>
#include <Wire.h>
#include "accel/accel.h"
#include "window/window.h"

void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);  // wait for USB CDC on XIAO

    Wire.begin();

    if (!accel_init()) {
        Serial.println("[ERROR] LIS3DHTR not found. Check wiring and I2C address.");
        while (true) delay(1000);
    }

    window_task_start();
    Serial.printf("[INFO] Sampling at %d Hz, window = %d s (%d samples)\n",
                  SAMPLE_RATE_HZ, WINDOW_DURATION_S, SAMPLES_PER_WINDOW);
}

void loop() {
    // Drain any completed windows and print them.
    float sum;
    while (window_pop(sum)) {
        Serial.printf("[WINDOW] magnitude sum = %.4f g\n", sum);
    }
    delay(100);
}
