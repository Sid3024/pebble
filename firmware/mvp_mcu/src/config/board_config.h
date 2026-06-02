#pragma once

// ================================================================
// mvp_mcu — XIAO ESP32-S3 board configuration
// ================================================================

// ── I2C / accelerometer ──────────────────────────────────────
// 1 = Seeed XIAO Expansion Board  (default Wire pins, SA0 HIGH → 0x19)
// 0 = Direct wiring SDA→D4 SCL→D5 (SA0 floating/GND → 0x18)
#define USE_EXPANSION_BOARD 1

#if USE_EXPANSION_BOARD
    #define ACCEL_I2C_ADDR  0x19
#else
    #define I2C_SDA         D4
    #define I2C_SCL         D5
    #define ACCEL_I2C_ADDR  0x18
#endif

// ── Vibration motor (LEDC PWM) ───────────────────────────────
// XIAO ESP32-S3 pin → GPIO reference:
//   D0=GPIO1  D1=GPIO2  D2=GPIO3  D7=GPIO7  D8=GPIO8  D9=GPIO9  D10=GPIO10
// Avoid D3/D4 in direct I2C mode. Currently wired to D0 (GPIO1).
#define VIBRATION_PIN           D0

#define VIBRATION_LEDC_CHANNEL  0       // LEDC channel 0–7
#define VIBRATION_LEDC_FREQ     1000    // Hz
#define VIBRATION_LEDC_RES      8       // bits — duty 0–255
