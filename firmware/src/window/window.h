/*
 * window.h — IMU Window Data Structures and Constants
 *
 * Defines the ImuWindow struct and ring buffer interface for the sampling
 * task. The firmware samples the IMU at 100Hz and averages every 25 samples
 * into one "window" (250ms). Windows are pushed into a lock-free ring buffer
 * and consumed by the main loop for BLE transmission.
 *
 * Key constants:
 *   SAMPLE_RATE_HZ      = 100   (10ms between samples)
 *   SAMPLES_PER_WINDOW  = 25    (250ms per window)
 *   WINDOW_BUFFER_SIZE  = 128   (~32 seconds of buffering)
 */

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
#define SAMPLES_PER_WINDOW  25
#define WINDOW_DURATION_S   ((float)SAMPLES_PER_WINDOW / SAMPLE_RATE_HZ)

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
