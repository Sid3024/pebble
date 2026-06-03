#pragma once
#include <Arduino.h>

/**
 * LIS3DHTR driver wrapper.
 *
 * accel_init() auto-detects the I2C address (tries 0x19 then 0x18),
 * so no recompile is needed when swapping between the expansion board
 * and direct wiring.  Call Wire.begin() before accel_init().
 */

bool accel_init();
bool accel_read(float &ax, float &ay, float &az);
