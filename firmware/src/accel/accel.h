#pragma once
#include <Arduino.h>
#include "config/board_config.h"

/**
 * Low-level LIS3DHTR driver wrapper.
 * Handles init and single-sample reads over I2C.
 *
 * I2C address and pins are controlled by config/board_config.h.
 */

bool accel_init();
bool accel_read(float &ax, float &ay, float &az);
