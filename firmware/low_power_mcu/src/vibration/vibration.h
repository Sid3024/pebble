#pragma once
#include <Arduino.h>
#include <constants.h>   // VIBR_* pattern IDs from shared/protocol

// ── Duty cycle (0–255, 8-bit analogWrite) ────────────────────
#define VIBRATION_DUTY_FULL  255   // 100 % — maximum motor drive
#define VIBRATION_DUTY_SOFT  160   //  63 % — lighter milestone taps

void vibration_init();
void vibration_play(uint8_t pattern_id);
