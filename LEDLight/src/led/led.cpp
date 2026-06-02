#include "led.h"
#include "config/led_config.h"
#include <FastLED.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

static CRGB s_leds[NUM_LEDS];

// Shared state (written by BLE callback, read by animation task)
static volatile uint8_t  s_ratio   = 128;   // 50/50 default
static volatile uint8_t  s_phase   = PHASE_WAITING;
static SemaphoreHandle_t s_mutex   = nullptr;

// Resolved team colours (built from config macros at init)
static CRGB TEAM0_COL;
static CRGB TEAM1_COL;

// ── Helpers ───────────────────────────────────────────────────

// Fill the strip for the "tug-of-war" playing state.
// boundary: float position in LED index space (0 – NUM_LEDS)
// A white spark pixel sits exactly at the boundary for the Harry-Potter effect.
static void render_playing(float boundary) {
    int bi = (int)boundary;

    for (int i = 0; i < NUM_LEDS; i++) {
        if (i < bi) {
            s_leds[i] = TEAM0_COL;
        } else if (i > bi) {
            s_leds[i] = TEAM1_COL;
        } else {
            // Boundary pixel — crackle between white and a mix of both teams
            uint8_t spark = beatsin8(120, 160, 255);   // 120 BPM oscillation
            s_leds[i]     = CRGB(spark, spark, spark);
        }
    }
}

// Waiting / non-competitive idle: dim half-and-half static split.
static void render_waiting() {
    int split = NUM_LEDS / 2;
    for (int i = 0; i < split; i++)        s_leds[i] = TEAM0_COL;
    for (int i = split; i < NUM_LEDS; i++) s_leds[i] = TEAM1_COL;
    // Dim for an "idle" look
    for (int i = 0; i < NUM_LEDS; i++) s_leds[i].nscale8(60);
}

// ── Animation task ────────────────────────────────────────────

static void led_task(void*) {
    float boundary  = NUM_LEDS / 2.0f;
    bool  blink_on  = true;
    uint32_t blink_last = 0;

    for (;;) {
        // Read shared state
        xSemaphoreTake(s_mutex, portMAX_DELAY);
        uint8_t ratio = s_ratio;
        uint8_t phase = s_phase;
        xSemaphoreGive(s_mutex);

        float target = (ratio / 255.0f) * (float)NUM_LEDS;

        switch (phase) {

            case PHASE_PLAYING:
                // Smoothly move boundary — creates the push/pull effect
                boundary += (target - boundary) * BOUNDARY_SMOOTH;
                render_playing(boundary);
                break;

            case PHASE_TEAM0_WIN:
            case PHASE_TEAM1_WIN:
            case PHASE_TIE: {
                // Celebratory blink — full strip at winner colour
                uint32_t now = millis();
                if (now - blink_last >= CELEBRATE_BLINK_MS) {
                    blink_on   = !blink_on;
                    blink_last = now;
                }
                if (phase == PHASE_TIE) {
                    // Alternate between both team colours
                    fill_solid(s_leds, NUM_LEDS, blink_on ? TEAM0_COL : TEAM1_COL);
                } else {
                    CRGB winner_col = (phase == PHASE_TEAM0_WIN) ? TEAM0_COL : TEAM1_COL;
                    fill_solid(s_leds, NUM_LEDS, blink_on ? winner_col : CRGB::Black);
                }
                break;
            }

            default:   // PHASE_WAITING and anything unknown
                render_waiting();
                break;
        }

        FastLED.show();
        vTaskDelay(pdMS_TO_TICKS(33));   // ~30 fps
    }
}

// ── Public API ────────────────────────────────────────────────

void led_init() {
    TEAM0_COL = CRGB(TEAM0_R, TEAM0_G, TEAM0_B);
    TEAM1_COL = CRGB(TEAM1_R, TEAM1_G, TEAM1_B);

    FastLED.addLeds<WS2812B, LED_DATA_PIN, GRB>(s_leds, NUM_LEDS);
    FastLED.setBrightness(LED_BRIGHTNESS);
    fill_solid(s_leds, NUM_LEDS, CRGB::Black);
    FastLED.show();

    s_mutex = xSemaphoreCreateMutex();
    Serial.printf("[LED] strip ready — %d LEDs on pin D%d\n", NUM_LEDS, LED_DATA_PIN);
}

void led_update(uint8_t ratio, uint8_t phase) {
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    s_ratio = ratio;
    s_phase = phase;
    xSemaphoreGive(s_mutex);
}

void led_task_start() {
    xTaskCreate(led_task, "led_anim", 4096, nullptr, 4, nullptr);
}
