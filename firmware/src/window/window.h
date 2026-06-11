#pragma once
#include <Arduino.h>
#include <stdint.h>

/**
 * Windowed IMU feature accumulator.
 *
 * A FreeRTOS task samples the MPU6050 at SAMPLE_RATE_HZ. Every completed
 * window stores movement direction, gyro direction, and pod angle summaries
 * for similarity scoring.
 */

#define SAMPLE_RATE_HZ      100
#define WINDOW_DURATION_S   1
#define SAMPLES_PER_WINDOW  (SAMPLE_RATE_HZ * WINDOW_DURATION_S)

#define WINDOW_BUFFER_SIZE  128

struct ImuWindow {
    uint16_t samples;
    float ax;
    float ay;
    float az;
    float gx;
    float gy;
    float gz;
    float roll;
    float pitch;
    float activity;
};

void window_task_start();
uint32_t window_available();
bool window_pop(ImuWindow &out);
