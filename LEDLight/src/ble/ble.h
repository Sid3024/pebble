/**
 * ============================================================================
 * LEDLight/src/ble/ble.h — BLE Interface Declarations for the LED Controller
 * ============================================================================
 *
 * PURPOSE:
 *   Declares the public API for the BLE (Bluetooth Low Energy) subsystem
 *   of the Pebble LED Light module. This header is included by main.cpp
 *   to set up BLE communication with the Python hub.
 *
 * HOW IT WORKS:
 *   The LED controller operates as a BLE PERIPHERAL (server). It advertises
 *   its presence with the name "PebbleLED_XXXXXX" (where XXXXXX is derived
 *   from the ESP32's Bluetooth MAC address). This naming convention allows
 *   the Python hub to distinguish LED controllers from game pods, which
 *   advertise as "Pebble_XXXXXX".
 *
 *   The BLE service exposes a single writable characteristic. The Python hub
 *   writes 2-byte commands to this characteristic at ~10Hz:
 *     byte[0] = ratio  — Score balance between teams:
 *                         0   = entire strip shows Team 2 color
 *                         128 = 50/50 split
 *                         255 = entire strip shows Team 1 color
 *     byte[1] = phase  — Current game phase (see PHASE_* constants in led/led.h):
 *                         0 = playing (tug-of-war animation)
 *                         1 = Team 1 wins (blue celebration blink)
 *                         2 = Team 2 wins (orange celebration blink)
 *                         3 = tie (alternating team colors)
 *                         4 = waiting (dim idle split)
 *
 * LIBRARIES:
 *   - Arduino.h — for uint8_t type definition
 *
 * FUNCTIONS DECLARED:
 *   - ble_led_set_callback() — Register a callback to receive BLE commands
 *   - ble_led_init()         — Initialize BLE and start advertising
 *   - ble_led_connected()    — Check if the Python hub is currently connected
 *
 * RELATIONSHIP TO PEBBLE PROJECT:
 *   The BLE UUIDs (service UUID and characteristic UUID) are defined in
 *   config/led_config.h and must match those used by the Python hub's
 *   LEDLight/client.py script, which discovers and writes to this device.
 * ============================================================================
 */

#pragma once
#include <Arduino.h>

/**
 * Callback function type for receiving LED commands from BLE.
 * Called when the Python hub writes a 2-byte command to the BLE characteristic.
 *
 * @param ratio  — Team balance (0 = all Team 2, 128 = 50/50, 255 = all Team 1)
 * @param phase  — Game phase constant (PHASE_PLAYING, PHASE_TEAM0_WIN, etc.)
 */
typedef void (*led_cmd_cb_t)(uint8_t ratio, uint8_t phase);

/**
 * Register the callback function that will be invoked when BLE commands arrive.
 * Must be called BEFORE ble_led_init() to ensure no commands are missed.
 */
void ble_led_set_callback(led_cmd_cb_t cb);

/**
 * Initialize the BLE peripheral: create server, service, characteristic,
 * and start advertising. The device name is auto-generated from the
 * ESP32's Bluetooth MAC address as "PebbleLED_XXXXXX".
 */
void ble_led_init();

/**
 * Check whether the Python hub is currently connected via BLE.
 * @returns true if a BLE central (the hub) is connected, false otherwise.
 */
bool ble_led_connected();
