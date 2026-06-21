/*
 * accel.h — IMU Driver Interface
 *
 * Thin wrapper around the MPU6050 (via Adafruit library) and MPU6500-family
 * (via raw I2C registers). Provides init, read, and diagnostic functions.
 * Supports auto-detection of chip type via WHO_AM_I register.
 */

#pragma once
#include <Arduino.h>
#include "config/board_config.h"

/**
 * Low-level MPU6050 IMU driver wrapper.
 * Handles init and single-sample reads over I2C.
 *
 * I2C address and pins are controlled by config/board_config.h.
 */

struct ImuSample {
    float ax;
    float ay;
    float az;
    float gx;
    float gy;
    float gz;
    float roll;
    float pitch;
};

bool imu_init();
bool imu_read(ImuSample &sample);

/**
 * Run I2C bus scan + WHO_AM_I probe + re-init attempt.
 * Prints findings to Serial. Returns true if re-init succeeded.
 * Call when consecutive read failures suggest the IMU has dropped off the bus.
 */
bool imu_diagnose();
