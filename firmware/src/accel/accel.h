#pragma once
#include <Arduino.h>

/**
 * Low-level LIS3DHTR driver wrapper.
 * Handles init and single-sample reads over I2C.
 */

// I2C address: 0x18 (SA0=GND) or 0x19 (SA0=VCC / LIS3DHTR_ADDRESS_UPDATED).
// The Seeed XIAO Expansion Board uses 0x19.
#define ACCEL_I2C_ADDRESS 0x19

/**
 * Initialise the LIS3DHTR and configure it for 100 Hz output.
 * Call Wire.begin() before this.
 * @return true on success, false if the device is not found.
 */
bool accel_init();

/**
 * Read one acceleration sample (units: g).
 * @param ax,ay,az  Output acceleration on each axis.
 * @return true if the read succeeded.
 */
bool accel_read(float &ax, float &ay, float &az);
