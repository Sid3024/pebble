#pragma once
#include <Arduino.h>

typedef void (*ble_command_cb_t)(uint8_t pattern_id);

void ble_set_command_callback(ble_command_cb_t cb);
void ble_init();
void ble_send_window(float window_sum);
bool ble_connected();
