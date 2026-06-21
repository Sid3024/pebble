/**
 * ============================================================================
 * LEDLight/src/main.cpp — Main Entry Point for the Pebble LED Strip Controller
 * ============================================================================
 *
 * PURPOSE:
 *   This is the main firmware file for the Pebble LED Light module, which
 *   runs on a XIAO ESP32S3 microcontroller. It drives a WS2812B LED strip
 *   that provides a physical, real-world visualization of the game state
 *   during Pebble Garden competitive mode.
 *
 * HOW IT WORKS:
 *   The firmware initializes three subsystems during setup():
 *     1. LED hardware — configures the FastLED library to drive the WS2812B
 *        strip and starts a FreeRTOS background task for animations.
 *     2. BLE callback — registers a lambda that forwards incoming BLE commands
 *        (ratio + phase bytes) to the LED animation system.
 *     3. BLE peripheral — advertises as "PebbleLED_XXXXXX" so the Python hub
 *        can discover and connect to it, then sends game state updates.
 *
 *   After setup, loop() does nothing meaningful. All real-time work happens
 *   in two asynchronous contexts:
 *     - The FreeRTOS LED animation task (runs at ~30fps, renders LED frames)
 *     - BLE characteristic write callbacks (triggered when the hub sends data)
 *
 * LIBRARIES:
 *   - Arduino.h — ESP32 Arduino framework for Serial, delay, pin definitions
 *   - ble/ble.h — BLE peripheral setup and command reception (see ble.cpp)
 *   - led/led.h — LED strip initialization and animation (see led.cpp)
 *
 * RELATIONSHIP TO PEBBLE PROJECT:
 *   This module is an optional accessory to the Pebble system. The Python hub
 *   (running on a laptop) connects to this ESP32S3 via BLE alongside the
 *   sensor pods. It sends a 2-byte command every ~100ms:
 *     byte[0] = ratio (0-255, Team 2 vs Team 1 balance)
 *     byte[1] = phase (playing, team0_win, team1_win, tie, waiting)
 *   The LED strip then shows a "tug-of-war" color effect during gameplay
 *   and celebratory blink patterns when a team wins.
 * ============================================================================
 */

#include <Arduino.h>
#include "ble/ble.h"
#include "led/led.h"

/**
 * Arduino setup — runs once at boot.
 *
 * Initialization order matters:
 *   1. Serial first (for debug logging)
 *   2. LED init + task start (so the strip shows the idle pattern immediately)
 *   3. BLE callback registration (before BLE init, so no commands are missed)
 *   4. BLE init (starts advertising, hub can connect)
 */
void setup() {
    Serial.begin(115200);
    // Wait up to 2 seconds for Serial to be ready (USB CDC on ESP32S3)
    while (!Serial && millis() < 2000) delay(10);

    // Initialize LED hardware (FastLED, pin, brightness) and start the
    // FreeRTOS animation task that renders frames at ~30fps
    led_init();
    led_task_start();

    // Wire BLE command reception to LED update — when the hub writes a
    // 2-byte command via BLE, this lambda extracts the ratio and phase
    // values and passes them to the LED animation system (thread-safe).
    ble_led_set_callback([](uint8_t ratio, uint8_t phase) {
        led_update(ratio, phase);
    });
    // Start BLE advertising so the Python hub can discover and connect
    ble_led_init();

    Serial.println("[MAIN] LED display ready — waiting for hub connection.");
}

/**
 * Arduino main loop — intentionally empty.
 *
 * All work is handled asynchronously:
 *   - LED rendering: FreeRTOS task "led_anim" (see led.cpp)
 *   - BLE communication: ESP32 BLE stack callbacks (see ble.cpp)
 * The 1-second delay prevents the watchdog timer from triggering
 * while keeping CPU usage minimal.
 */
void loop() {
    delay(1000);
}
