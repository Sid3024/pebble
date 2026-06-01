#pragma once
#include <Arduino.h>
#include "config/board_config.h"

/**
 * Low-level LIS3DHTR driver wrapper.
 * Handles init and single-sample reads over I2C.
 *
 * I2C address and pins are controlled by config/board_config.h.
 */

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
