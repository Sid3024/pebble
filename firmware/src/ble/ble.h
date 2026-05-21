#pragma once
#include <Arduino.h>

/**
 * BLE peripheral module.
 *
 * Advertises this device as "Pebble_XXXXXX" (last 3 bytes of BT MAC).
 * Exposes a single notify characteristic; call ble_send_window() each time
 * a 5-second window sum is ready.
 */

void ble_init();
void ble_send_window(float window_sum);
bool ble_connected();
