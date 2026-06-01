#pragma once
#include <Arduino.h>

// ── Duty cycle (0 – 255 at 8-bit LEDC resolution) ────────────
// Full power is used for team-assignment patterns and the win sequence.
// Soft power is used for the gentler mid-game milestone taps.
// Increase these values for a stronger motor; decrease for a weaker one.
#define VIBRATION_DUTY_FULL  255   // 100 % — maximum motor drive for team assignment
#define VIBRATION_DUTY_SOFT  255   //  63 % — lighter milestone feedback for in game

// ── Pattern IDs — must match ble/constants.py exactly ────────
#define VIBR_TEAM1       1   // 5 s — team 1 assignment  (quick triple tap)
#define VIBR_TEAM2       2   // 5 s — team 2 assignment  (long-short)
#define VIBR_MILESTONE1  3   // ~0.6 s — 25 % progress  (two gentle taps)
#define VIBR_MILESTONE2  4   // ~1.2 s — 50 % progress  (three medium pulses)
#define VIBR_MILESTONE3  5   // ~1.2 s — 75 % progress  (four quick taps)
#define VIBR_WIN         6   // ~1.7 s — full bloom/win  (rapid burst + hold)
#define VIBR_FLOWER_50   7   // ~0.7 s — every 50 flowers (happy double-tap + hold)

/**
 * Initialise the vibration motor GPIO. Call once in setup().
 */
void vibration_init();

/**
 * Play a vibration pattern by ID (see defines above).
 * Runs in a background FreeRTOS task; cancels any currently-playing pattern.
 */
void vibration_play(uint8_t pattern_id);
