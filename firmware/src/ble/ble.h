/*
 * ble.h — BLE GATT Server Interface for Pebble Pods
 *
 * Defines the BLE service layout:
 *   - One service with two characteristics:
 *     1. WINDOW_CHAR (notify): Pod sends 20-byte IMU windows to the host.
 *     2. COMMAND_CHAR (write): Host sends 1-byte vibration pattern IDs to the pod.
 *   - Device name = "Pebble_" + last 3 bytes of MAC address (unique per pod).
 *   - Auto-restarts advertising on disconnect.
 */

#pragma once
#include <Arduino.h>

/**
 * BLE peripheral module.
 *
 * Advertises as "Pebble_XXXXXX" (last 3 bytes of BT MAC).
 *
 * Characteristics
 *   WINDOW_CHAR  (notify) - MCU -> central: 20-byte IMU window packet
 *   COMMAND_CHAR (write)  - central -> MCU: 1-byte vibration pattern ID
 */

struct ImuWindow;

typedef void (*ble_command_cb_t)(uint8_t pattern_id);

void ble_set_command_callback(ble_command_cb_t cb);
void ble_init();
void ble_send_window(const ImuWindow &window);
// Send a 3-byte status/error packet (magic=0xE1, error_code).
// 0x01 = IMU offline, 0x02 = IMU init failed, 0x03 = IMU read failures.
void ble_send_status(uint8_t error_code);
bool ble_connected();
