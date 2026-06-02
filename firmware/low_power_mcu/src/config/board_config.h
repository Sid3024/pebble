#pragma once

// ================================================================
// low_power_mcu — XIAO nRF52840 (Plus) board configuration
// ================================================================

// ── I2C / accelerometer ──────────────────────────────────────
// On nRF52840, Wire defaults to D4 (SDA) and D5 (SCL) — same pins
// whether using the expansion board or direct wiring — so no
// conditional Wire.begin() call is needed.
//
// 1 = expansion board  (SA0 pulled HIGH → address 0x19)
// 0 = direct wiring    (SA0 floating/GND → address 0x18)
#define USE_EXPANSION_BOARD 1

#if USE_EXPANSION_BOARD
    #define ACCEL_I2C_ADDR  0x19
#else
    #define ACCEL_I2C_ADDR  0x18
#endif

// ── Vibration motor (analogWrite PWM) ────────────────────────
// nRF52840 Arduino framework uses analogWrite() for PWM.
// No LEDC configuration required.
// nRF52840 XIAO pin reference: D0=P0.02  D1=P0.03  D2=P0.28
// Avoid D4/D5 (I2C). Currently wired to D0.
#define VIBRATION_PIN   D0
