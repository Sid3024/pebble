#include <Arduino.h>
#include "ble/ble.h"
#include "led/led.h"

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) delay(10);

    led_init();
    led_task_start();

    // Wire BLE command → LED update
    ble_led_set_callback([](uint8_t ratio, uint8_t phase) {
        led_update(ratio, phase);
    });
    ble_led_init();

    Serial.println("[MAIN] LED display ready — waiting for hub connection.");
}

void loop() {
    // All work happens in the FreeRTOS led_task and BLE callbacks.
    delay(1000);
}
