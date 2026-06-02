#pragma once
#include <Arduino.h>

// Phase values — must match LEDLight/client.py exactly
#define PHASE_PLAYING    0   // competitive game in progress
#define PHASE_TEAM0_WIN  1   // Team 1 wins — celebrate blue
#define PHASE_TEAM1_WIN  2   // Team 2 wins — celebrate orange
#define PHASE_TIE        3   // tie — alternate colours
#define PHASE_WAITING    4   // not in competitive mode

/**
 * Initialise the FastLED strip. Call once in setup().
 */
void led_init();

/**
 * Update the target ratio and phase. Thread-safe — can be called from BLE callback.
 *   ratio 0   = entire strip Team 2 colour
 *   ratio 128 = 50 / 50
 *   ratio 255 = entire strip Team 1 colour
 */
void led_update(uint8_t ratio, uint8_t phase);

/**
 * Start the background FreeRTOS animation task. Call after led_init().
 */
void led_task_start();
