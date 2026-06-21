/**
 * ============================================================================
 * LEDLight/src/led/led.h — LED Animation Interface for the Pebble LED Light
 * ============================================================================
 *
 * PURPOSE:
 *   Declares the public API for the LED animation subsystem and defines
 *   the game phase constants. This header is included by both main.cpp
 *   (to call the API) and led.cpp (to implement it).
 *
 * HOW IT WORKS:
 *   The LED subsystem has three entry points:
 *     1. led_init()       — One-time hardware setup (FastLED, pin, brightness)
 *     2. led_task_start() — Launch the background animation FreeRTOS task
 *     3. led_update()     — Thread-safe setter for ratio and phase values
 *
 *   The animation task runs continuously at ~30fps, reading the current
 *   ratio and phase to determine what pattern to display on the LED strip:
 *     - PHASE_PLAYING:   Tug-of-war effect with a moving color boundary
 *     - PHASE_TEAM0_WIN: Full strip blinks Team 1 color (blue)
 *     - PHASE_TEAM1_WIN: Full strip blinks Team 2 color (orange)
 *     - PHASE_TIE:       Strip alternates between both team colors
 *     - PHASE_WAITING:   Dim static split (half blue, half orange)
 *
 * GAME PHASE CONSTANTS:
 *   These integer constants encode the current game phase. They must match
 *   the values used in the Python hub (LEDLight/client.py), which maps
 *   the game server's string phases to these numeric values before sending
 *   them over BLE.
 *
 * THREAD SAFETY:
 *   led_update() is designed to be called from any context (including BLE
 *   callbacks running on the BLE task). It uses a FreeRTOS mutex internally
 *   to safely share data with the animation task.
 *
 * RELATIONSHIP TO PEBBLE PROJECT:
 *   This subsystem translates numeric game state (ratio + phase) into
 *   physical LED animations, providing a tangible complement to the
 *   GameDashboard's on-screen flower visualization.
 * ============================================================================
 */

#pragma once
#include <Arduino.h>

// ── Game phase constants ────────────────────────────────────
// These numeric values are sent as byte[1] of the BLE command from the
// Python hub. They MUST match the encoding in LEDLight/client.py exactly.
#define PHASE_PLAYING    0   // Competitive game in progress — show tug-of-war effect
#define PHASE_TEAM0_WIN  1   // Team 1 (blue) wins — celebratory blink in blue
#define PHASE_TEAM1_WIN  2   // Team 2 (orange) wins — celebratory blink in orange
#define PHASE_TIE        3   // Scores are tied — alternate between both team colors
#define PHASE_WAITING    4   // No competitive game active — dim idle split pattern

/**
 * Initialize the FastLED library and configure the WS2812B LED strip.
 *
 * Sets up:
 *   - LED data pin and strip type (WS2812B, GRB color order)
 *   - Global brightness limit
 *   - Team color CRGB values from config macros
 *   - FreeRTOS mutex for thread-safe state sharing
 *   - Initial state: all LEDs off (black)
 *
 * Must be called once in setup(), before led_task_start().
 */
void led_init();

/**
 * Update the target score ratio and game phase. Thread-safe.
 *
 * Can be safely called from any context, including BLE callbacks.
 * Uses a FreeRTOS mutex to protect the shared state variables.
 *
 * @param ratio — Score balance between teams:
 *                0   = entire strip shows Team 2 color
 *                128 = 50/50 split at the middle
 *                255 = entire strip shows Team 1 color
 * @param phase — One of the PHASE_* constants defined above
 */
void led_update(uint8_t ratio, uint8_t phase);

/**
 * Start the background FreeRTOS animation task ("led_anim").
 *
 * This task runs an infinite loop at ~30fps (33ms per frame), reading
 * the current ratio/phase and rendering the appropriate LED pattern.
 * Must be called after led_init() so the strip and mutex are ready.
 *
 * Task parameters:
 *   - Stack size: 4096 bytes
 *   - Priority: 4 (above default but below critical system tasks)
 */
void led_task_start();
