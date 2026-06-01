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
//         Accelerometer SA0 floating/GND → address 0x18
//         (if your module pulls SA0 high, change ACCEL_I2C_ADDR to 0x19)
// ================================================================
#define USE_EXPANSION_BOARD 1 // 0-> direct wiring, 1 -> i2c via exp board

// ── Vibration motor (LEDC PWM) ───────────────────────────────
// GPIO driving the vibration motor via transistor/MOSFET gate.
// Change VIBRATION_PIN to match your wiring.
//
// XIAO ESP32-S3 digital pin → GPIO reference:
//   D0=GPIO1  D1=GPIO2  D2=GPIO3  D3=GPIO4  D4=GPIO5
//   D5=GPIO43 D6=GPIO44 D7=GPIO7  D8=GPIO8  D9=GPIO9  D10=GPIO10
//
// Avoid: D3/D4 when USE_EXPANSION_BOARD=0 (I2C SDA/SCL), D5/D6 (UART TX/RX).
#define VIBRATION_PIN          D0   // wired to D0 (GPIO1)

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
    #define ACCEL_I2C_ADDR  0x18
#endif

