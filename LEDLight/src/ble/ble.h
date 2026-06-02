#pragma once
#include <Arduino.h>

/**
 * BLE peripheral for the LED display MCU.
 *
 * Advertises as "PebbleLED_XXXXXX" so the Python hub can identify it
 * separately from the game pods ("Pebble_XXXXXX").
 *
 * Single writable characteristic receives 2-byte commands:
 *   byte[0] ratio  — 0 = all Team 2, 128 = 50/50, 255 = all Team 1
 *   byte[1] phase  — see PHASE_* constants in led/led.h
 */

typedef void (*led_cmd_cb_t)(uint8_t ratio, uint8_t phase);

void ble_led_set_callback(led_cmd_cb_t cb);
void ble_led_init();
bool ble_led_connected();
