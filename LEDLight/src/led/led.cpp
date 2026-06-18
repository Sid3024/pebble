/**
 * ============================================================================
 * LEDLight/src/led/led.cpp — LED Animation Patterns for the Pebble LED Light
 * ============================================================================
 *
 * PURPOSE:
 *   Implements all LED animation patterns for the Pebble LED Light module.
 *   Translates game state (ratio + phase) received via BLE into real-time
 *   LED strip animations using the FastLED library.
 *
 * HOW IT WORKS:
 *   The animation system runs as a FreeRTOS background task at ~30fps.
 *   Each frame, it reads the current ratio and phase (set by BLE callbacks
 *   via led_update), then renders the appropriate pattern:
 *
 *   PLAYING (tug-of-war):
 *     The strip displays a split of two team colors. The boundary between
 *     the colors smoothly slides left/right based on the score ratio.
 *     A bright white "spark" pixel sits at the boundary for visual emphasis
 *     (inspired by dueling wand effects). The boundary movement is smoothed
 *     using linear interpolation (lerp) at BOUNDARY_SMOOTH rate to create
 *     a fluid push/pull effect rather than jumpy transitions.
 *
 *   TEAM0_WIN / TEAM1_WIN (celebration):
 *     The entire strip blinks between the winning team's color and black.
 *     The blink rate is CELEBRATE_BLINK_MS per half-cycle.
 *
 *   TIE (alternating celebration):
 *     The entire strip alternates between Team 1 and Team 2 colors at
 *     the same blink rate.
 *
 *   WAITING (idle):
 *     A dim, static split showing both team colors at reduced brightness
 *     (about 23% via nscale8(60)). This serves as a "standby" indicator.
 *
 * LIBRARIES:
 *   - FastLED.h — Industry-standard library for controlling addressable
 *     LED strips (WS2812B in this case). Provides CRGB color type,
 *     fill_solid, beatsin8, nscale8, and the show() method.
 *   - FreeRTOS (task.h, semphr.h) — For creating the background animation
 *     task and the mutex that protects shared state between the BLE
 *     callback context and the animation task.
 *   - led.h — Phase constants and public API declarations.
 *   - config/led_config.h — Hardware configuration (pin, count, colors,
 *     animation parameters, BLE UUIDs).
 *
 * THREAD SAFETY:
 *   The ratio and phase variables are written by BLE callbacks (running on
 *   the ESP32 BLE task) and read by the animation task. A FreeRTOS mutex
 *   protects these shared variables. Both volatile and mutex are used:
 *   volatile prevents compiler optimization of the reads, and the mutex
 *   provides atomic access guarantees.
 *
 * SECTIONS:
 *   1. Module state — LED buffer, shared variables, team colors
 *   2. render_playing() — Tug-of-war split with spark boundary
 *   3. render_waiting() — Dim idle pattern
 *   4. led_task() — Main animation loop (FreeRTOS task function)
 *   5. Public API — led_init(), led_update(), led_task_start()
 *
 * RELATIONSHIP TO PEBBLE PROJECT:
 *   This is the physical output counterpart to the GameDashboard's on-screen
 *   flower garden. While the dashboard shows growing flowers, the LED strip
 *   shows a real-time "territory" visualization of the competitive game
 *   score. Both receive their data from the same Python hub.
 * ============================================================================
 */

#include "led.h"
#include "config/led_config.h"
#include <FastLED.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

/* FastLED pixel buffer — each CRGB element represents one LED's color.
   FastLED.show() copies this buffer to the physical strip via the data pin. */
static CRGB s_leds[NUM_LEDS];

/* Shared state variables — written by led_update() (BLE context),
   read by led_task() (animation context). Protected by s_mutex.
   volatile ensures the compiler doesn't cache these in registers. */
static volatile uint8_t  s_ratio   = 128;          // Score ratio (default: 50/50)
static volatile uint8_t  s_phase   = PHASE_WAITING; // Game phase (default: idle)
static SemaphoreHandle_t s_mutex   = nullptr;       // Protects s_ratio and s_phase

/* Team colors resolved from config macros into CRGB objects at init time.
   Stored as module-level variables so they're computed once, not every frame. */
static CRGB TEAM0_COL;   // Team 1 color (blue by default)
static CRGB TEAM1_COL;   // Team 2 color (orange by default)

// ── Render helpers ────────────────────────────────────────────

/**
 * Render the "tug-of-war" playing animation.
 *
 * Splits the LED strip into two colored regions (Team 0 and Team 1)
 * with a moving boundary. The boundary position is a float in LED
 * index space (0.0 to NUM_LEDS), allowing sub-pixel precision.
 *
 * LED coloring logic:
 *   - LEDs to the left of boundary (-0.5 threshold) = Team 0 color
 *   - LEDs to the right of boundary (+0.5 threshold) = Team 1 color
 *   - The LED at the boundary = white "spark" pixel
 *
 * The spark is a pulsating white pixel (brightness oscillates 160-255
 * using FastLED's beatsin8 at 120 BPM) that creates a "dueling wands"
 * visual effect at the color boundary.
 *
 * Edge case handling:
 *   When one team dominates completely (boundary near 0 or NUM_LEDS),
 *   the spark is suppressed and the boundary LED shows the dominant
 *   team's color instead. This prevents a lone white pixel at the
 *   strip's edge, which would look like a glitch.
 *
 * @param boundary — Float position of the color split (0.0 to NUM_LEDS)
 */
static void render_playing(float boundary) {
    // Detect when boundary is at the extremes (one team has all LEDs)
    bool at_start = boundary < 0.5f;
    bool at_end   = boundary > (NUM_LEDS - 1.5f);

    for (int i = 0; i < NUM_LEDS; i++) {
        float f = (float)i - boundary;
        if (f < -0.5f) {
            s_leds[i] = TEAM0_COL;         // Left of boundary = Team 0
        } else if (f > 0.5f) {
            s_leds[i] = TEAM1_COL;         // Right of boundary = Team 1
        } else {
            // This LED is at the boundary
            if (at_start) {
                s_leds[i] = TEAM1_COL;      // All Team 2 — no spark
            } else if (at_end) {
                s_leds[i] = TEAM0_COL;      // All Team 1 — no spark
            } else {
                // Pulsating white spark at the boundary
                uint8_t spark = beatsin8(120, 160, 255);
                s_leds[i]     = CRGB(spark, spark, spark);
            }
        }
    }
}

/**
 * Render the idle/waiting pattern — a dim, static half-and-half split.
 *
 * The first half of the strip shows Team 0 color, the second half shows
 * Team 1 color. Both are dimmed to ~23% brightness (nscale8(60) scales
 * each color component by 60/256) to create a subtle "standby" appearance
 * that indicates the strip is working but no game is active.
 */
static void render_waiting() {
    int split = NUM_LEDS / 2;
    for (int i = 0; i < split; i++)        s_leds[i] = TEAM0_COL;
    for (int i = split; i < NUM_LEDS; i++) s_leds[i] = TEAM1_COL;
    // Scale down brightness for an "idle" look
    for (int i = 0; i < NUM_LEDS; i++) s_leds[i].nscale8(60);
}

// ── Animation task ────────────────────────────────────────────

/**
 * Main animation loop — runs as a FreeRTOS task at ~30fps.
 *
 * This function never returns. Each iteration:
 *   1. Takes the mutex and copies ratio + phase from shared state
 *   2. Computes the target boundary position from the ratio
 *   3. Renders the appropriate pattern based on the current phase
 *   4. Pushes the pixel buffer to the physical LED strip via FastLED.show()
 *   5. Sleeps for 33ms (~30fps) to yield CPU time to other tasks
 *
 * Local state:
 *   - boundary: smoothed float position of the color split (persists between frames)
 *   - blink_on: toggle state for celebration blink (persists between frames)
 *   - blink_last: timestamp of last blink toggle
 *
 * Animation modes by phase:
 *
 *   PLAYING: The boundary smoothly moves toward the target using a lerp
 *     (linear interpolation) with BOUNDARY_SMOOTH as the blend factor.
 *     This creates a fluid push/pull effect rather than jumpy transitions.
 *     Example: if boundary=15 and target=20, next frame boundary becomes
 *     15 + (20-15) * 0.06 = 15.3 — a gradual drift toward the target.
 *
 *   TEAM0_WIN / TEAM1_WIN: The strip blinks between the winner's color
 *     and black. Uses millis() timestamps rather than a frame counter
 *     to ensure consistent blink timing regardless of frame rate.
 *
 *   TIE: Same blink timing but alternates between Team 0 and Team 1
 *     colors (never black), creating a "both teams celebrate" effect.
 *
 *   WAITING (default): Static dim split pattern via render_waiting().
 *     Any unknown phase values also fall through to this default.
 *
 * @param unused — FreeRTOS task parameter (not used)
 */
static void led_task(void*) {
    float boundary  = NUM_LEDS / 2.0f;  // Start with boundary at center
    bool  blink_on  = true;              // Blink toggle for celebrations
    uint32_t blink_last = 0;             // Timestamp of last blink toggle

    for (;;) {
        // ── Step 1: Read shared state under mutex protection ──
        xSemaphoreTake(s_mutex, portMAX_DELAY);
        uint8_t ratio = s_ratio;
        uint8_t phase = s_phase;
        xSemaphoreGive(s_mutex);

        // Convert ratio (0-255) to a float position in LED index space (0 to NUM_LEDS)
        float target = (ratio / 255.0f) * (float)NUM_LEDS;

        // ── Step 2: Render the appropriate pattern ──
        switch (phase) {

            case PHASE_PLAYING:
                // Smoothly lerp boundary toward target — creates the push/pull effect
                boundary += (target - boundary) * BOUNDARY_SMOOTH;
                render_playing(boundary);
                break;

            case PHASE_TEAM0_WIN:
            case PHASE_TEAM1_WIN:
            case PHASE_TIE: {
                // Celebration blink using timestamp-based timing
                uint32_t now = millis();
                if (now - blink_last >= CELEBRATE_BLINK_MS) {
                    blink_on   = !blink_on;
                    blink_last = now;
                }
                if (phase == PHASE_TIE) {
                    // Tie: alternate between both team colors (no black)
                    fill_solid(s_leds, NUM_LEDS, blink_on ? TEAM0_COL : TEAM1_COL);
                } else {
                    // Win: blink winner color on/off (with black)
                    CRGB winner_col = (phase == PHASE_TEAM0_WIN) ? TEAM0_COL : TEAM1_COL;
                    fill_solid(s_leds, NUM_LEDS, blink_on ? winner_col : CRGB::Black);
                }
                break;
            }

            default:   // PHASE_WAITING and any unknown phase values
                render_waiting();
                break;
        }

        // ── Step 3: Push pixel buffer to physical LED strip ──
        FastLED.show();

        // ── Step 4: Sleep until next frame (~30fps) ──
        vTaskDelay(pdMS_TO_TICKS(33));
    }
}

// ── Public API ────────────────────────────────────────────────

/**
 * Initialize the LED strip hardware and prepare for animation.
 *
 * Steps:
 *   1. Build CRGB color objects from the config macros (TEAM0_R/G/B, etc.)
 *   2. Register the WS2812B strip with FastLED:
 *      - Template params: WS2812B chip type, data pin, GRB color order
 *        (WS2812B uses Green-Red-Blue byte order, not RGB)
 *      - Binds the s_leds pixel buffer to the strip
 *   3. Set global brightness limit (protects against overcurrent)
 *   4. Clear all LEDs to black and push to strip (clean startup)
 *   5. Create the FreeRTOS mutex for thread-safe state sharing
 */
void led_init() {
    // Convert config macros to CRGB objects
    TEAM0_COL = CRGB(TEAM0_R, TEAM0_G, TEAM0_B);
    TEAM1_COL = CRGB(TEAM1_R, TEAM1_G, TEAM1_B);

    // Register strip: WS2812B type, data pin, GRB color order
    FastLED.addLeds<WS2812B, LED_DATA_PIN, GRB>(s_leds, NUM_LEDS);
    FastLED.setBrightness(LED_BRIGHTNESS);
    // Start with all LEDs off
    fill_solid(s_leds, NUM_LEDS, CRGB::Black);
    FastLED.show();

    // Create mutex for protecting shared state between tasks
    s_mutex = xSemaphoreCreateMutex();
    Serial.printf("[LED] strip ready — %d LEDs on pin D%d\n", NUM_LEDS, LED_DATA_PIN);
}

/**
 * Thread-safe update of the target ratio and game phase.
 *
 * Called from the BLE callback context (via the lambda registered in main.cpp).
 * Takes the mutex to atomically update both values, ensuring the animation
 * task always sees a consistent pair of ratio + phase.
 *
 * @param ratio — Score balance (0 = all Team 2, 128 = 50/50, 255 = all Team 1)
 * @param phase — Game phase (PHASE_PLAYING, PHASE_TEAM0_WIN, etc.)
 */
void led_update(uint8_t ratio, uint8_t phase) {
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    s_ratio = ratio;
    s_phase = phase;
    xSemaphoreGive(s_mutex);
}

/**
 * Launch the background animation task on FreeRTOS.
 *
 * Creates a new task "led_anim" that runs led_task() in an infinite loop.
 *   - Stack: 4096 bytes (sufficient for FastLED rendering + local variables)
 *   - Priority: 4 (above idle/default, below WiFi/BLE system tasks)
 *   - No task handle stored (we never need to suspend or delete this task)
 *
 * Must be called after led_init() to ensure the strip and mutex are ready.
 */
void led_task_start() {
    xTaskCreate(led_task, "led_anim", 4096, nullptr, 4, nullptr);
}
