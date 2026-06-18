#pragma once

// ================================================================
// Board configuration
// ================================================================
// Set USE_EXPANSION_BOARD to select the hardware wiring:
//
//   1 - Seeed XIAO Expansion Board
//       I2C routed through the Grove connector (default Wire pins)
//       MPU6050 AD0 pulled LOW -> address 0x68, HIGH -> 0x69
//
//   0 - Direct wiring to MCU pins
//       IMU VCC  -> 3V3
//       IMU GND  -> GND
//       IMU SDA  -> D4/GPIO5
//       IMU SCL  -> D5/GPIO6
//       IMU INT1 -> D3/GPIO4
//       Motor VM -> external motor supply, e.g. 5V for a 5V motor
//       Motor GND shared with MCU GND
//       Motor IN/PWM -> D9/GPIO8
//       MPU6050 AD0 pulled LOW -> address 0x68, HIGH -> 0x69
// ================================================================
#define USE_EXPANSION_BOARD 0 // 0 -> direct wiring, 1 -> I2C via expansion board

// Vibration motor (LEDC PWM)
#define VIBRATION_PIN          D9   // motor IN/PWM wired to D9/GPIO8
#define VIBRATION_LEDC_CHANNEL 0    // LEDC channel 0-7
#define VIBRATION_LEDC_FREQ    1000 // Hz
#define VIBRATION_LEDC_RES     8    // bits, duty 0-255

// Derived IMU I2C settings.
#if USE_EXPANSION_BOARD
    // No explicit pins; Wire.begin() uses the board's default SDA/SCL.
    #define IMU_I2C_ADDR    0x68
    #define IMU_I2C_ADDR_ALT 0x69
#else
    #define I2C_SDA         D4
    #define I2C_SCL         D5
    #define IMU_INT_PIN     D3
    #define IMU_I2C_ADDR    0x68
    #define IMU_I2C_ADDR_ALT 0x69
#endif
