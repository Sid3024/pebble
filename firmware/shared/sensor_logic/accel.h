#pragma once
#include <Arduino.h>

/**
 * Platform-agnostic LIS3DHTR driver wrapper.
 * Wire.begin() must be called before accel_init().
 * The I2C address is passed in by main.cpp (from board_config.h),
 * keeping this file free of any MCU-specific configuration.
 */

/**
 * Initialise the LIS3DHTR at the given I2C address (0x18 or 0x19).
 * @return true on success, false if the sensor is not found.
 */
bool accel_init(uint8_t i2c_addr);

/**
 * Read one acceleration sample (units: g).
 * @param ax, ay, az  Output values per axis.
 * @return true if read succeeded.
 */
bool accel_read(float &ax, float &ay, float &az);
