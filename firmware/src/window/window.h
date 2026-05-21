#pragma once
#include <Arduino.h>
#include <stdint.h>

/**
 * Windowed magnitude accumulator for the accelerometer.
 *
 * A FreeRTOS task samples the accelerometer at SAMPLE_RATE_HZ.
 * Each sample contributes its vector magnitude sqrt(ax²+ay²+az²) to a
 * running sum. Every WINDOW_DURATION_S seconds the completed sum is pushed
 * into a fixed-size ring buffer for consumption by the main task.
 */

#define SAMPLE_RATE_HZ      100
#define WINDOW_DURATION_S   5
#define SAMPLES_PER_WINDOW  (SAMPLE_RATE_HZ * WINDOW_DURATION_S)  // 500

// How many completed windows to keep before the oldest is overwritten.
#define WINDOW_BUFFER_SIZE  128

/**
 * Create the FreeRTOS sampling task.
 * accel_init() must succeed before calling this.
 */
void window_task_start();

/**
 * Number of completed windows waiting in the buffer.
 * Thread-safe — may be called from any task.
 */
uint32_t window_available();

/**
 * Consume and return the oldest completed window sum.
 * @param out  Receives the sum of magnitudes (g) over the window.
 * @return     false if the buffer is empty.
 */
bool window_pop(float &out);
