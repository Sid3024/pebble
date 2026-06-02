#pragma once

// ================================================================
// LED display configuration — edit this file to match your hardware
// ================================================================

// ── LED strip ────────────────────────────────────────────────
#define NUM_LEDS        30          // number of LEDs in your strip
#define LED_DATA_PIN    D1          // data pin connected to strip DIN
#define LED_BRIGHTNESS  80          // 0–255 (keep under 150 to avoid overcurrent)

// ── Team colours (R, G, B) ───────────────────────────────────
#define TEAM0_R   0
#define TEAM0_G  80
#define TEAM0_B  255    // Team 1 — blue

#define TEAM1_R  255
#define TEAM1_G   80
#define TEAM1_B    0    // Team 2 — orange

// ── Animation ────────────────────────────────────────────────
// How quickly the colour boundary moves (0–1).
// Lower = slower / more dramatic push; higher = snappier response.
#define BOUNDARY_SMOOTH   0.06f

// Blink period for the celebration animation (ms per half-cycle).
#define CELEBRATE_BLINK_MS  350

// ── BLE UUIDs — must match LEDLight/client.py exactly ────────
#define LED_SERVICE_UUID  "b1c2d3e4-f5a6-7890-abcd-ef1234567890"
#define LED_CMD_UUID      "b1c2d3e4-f5a6-7890-abcd-ef1234567891"
