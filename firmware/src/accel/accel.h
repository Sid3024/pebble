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
