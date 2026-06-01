#pragma once
#include <Arduino.h>

/**
 * BLE peripheral module.
 *
 * Advertises as "Pebble_XXXXXX" (last 3 bytes of BT MAC).
 *
 * Characteristics
 *   WINDOW_CHAR  (notify) — MCU → central: 4-byte LE float window sum
 *   COMMAND_CHAR (write)  — central → MCU: 1-byte vibration pattern ID
 *
 * Register a command callback before calling ble_init().
 */

typedef void (*ble_command_cb_t)(uint8_t pattern_id);

void ble_set_command_callback(ble_command_cb_t cb);
void ble_init();
void ble_send_window(float window_sum);
bool ble_connected();
