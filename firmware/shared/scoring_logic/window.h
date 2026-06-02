#pragma once
#include <Arduino.h>
#include <stdint.h>

// ── Sampling parameters ───────────────────────────────────────
#define SAMPLE_RATE_HZ      100
#define WINDOW_DURATION_S   3
#define SAMPLES_PER_WINDOW  (SAMPLE_RATE_HZ * WINDOW_DURATION_S)   // 300

// ── Ring buffer capacity ──────────────────────────────────────
#define WINDOW_BUFFER_SIZE  128

/**
 * Start the FreeRTOS window-sampling task.
 * accel_init() must have been called before this.
 */
void window_task_start();

/** Number of completed windows waiting to be consumed. */
uint32_t window_available();

/**
 * Pop the oldest completed window sum.
 * @param out  Receives the sum of |acceleration| magnitudes over the window.
 * @return true if a value was available, false if the buffer was empty.
 */
bool window_pop(float &out);
