#pragma once

// ================================================================
// Board configuration
// ================================================================
// Set USE_EXPANSION_BOARD to select the hardware wiring:
//
//   1 — Seeed XIAO Expansion Board
//         I2C routed through the Grove connector (default Wire pins)
//         Accelerometer SA0 pulled HIGH → address 0x19
//
//   0 — Direct wiring to MCU pins
//         SDA → D4   SCL → D5
//         Accelerometer SA0 pulled HIGH → address 0x19
// ================================================================
#define USE_EXPANSION_BOARD 0 // 0-> direct wiring, 1 -> i2c via exp board

// ── Vibration motor (LEDC PWM) ───────────────────────────────
// GPIO driving the vibration motor via transistor/MOSFET gate.
// Change VIBRATION_PIN to match your wiring.
//
// XIAO ESP32-S3 digital pin → GPIO reference:
//   D0=GPIO1  D1=GPIO2  D2=GPIO3  D3=GPIO4  D4=GPIO5
//   D5=GPIO6  D6=GPIO43 D7=GPIO44 D8=GPIO7  D9=GPIO8  D10=GPIO9
//
// Avoid: D4/D5 when USE_EXPANSION_BOARD=0 (I2C SDA/SCL), D6/D7 (UART TX/RX).
#define VIBRATION_PIN          D9   // wired to D9 (GPIO8)

// LEDC peripheral config
#define VIBRATION_LEDC_CHANNEL 0        // LEDC channel 0–7
#define VIBRATION_LEDC_FREQ    1000     // Hz — 1 kHz is above audible buzz range
#define VIBRATION_LEDC_RES     8        // bits — duty 0–255


// ── Derived I2C settings ─────────────────────────────────────
#if USE_EXPANSION_BOARD
    // No explicit pins — Wire.begin() uses the board's default SDA/SCL
    #define ACCEL_I2C_ADDR  0x19
#else
    #define I2C_SDA         D4
    #define I2C_SCL         D5
    #define ACCEL_I2C_ADDR  0x19
#endif

