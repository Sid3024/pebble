#include <Arduino.h>
#include <Wire.h>
#include "config/board_config.h"
#include "accel/accel.h"
#include "window/window.h"
#include "ble/ble.h"
#include "vibration/vibration.h"

static bool s_accel_ok = false;

// ── I2C pin mapping ───────────────────────────────────────────
#if USE_EXPANSION_BOARD
  static const int PIN_SCL = SCL;
  static const int PIN_SDA = SDA;
#else
  static const int PIN_SCL = I2C_SCL;
  static const int PIN_SDA = I2C_SDA;
#endif

// ── I2C bus recovery ──────────────────────────────────────────
static void i2c_recover() {
    Wire.end();

    pinMode(PIN_SCL, OUTPUT_OPEN_DRAIN);
    pinMode(PIN_SDA, OUTPUT_OPEN_DRAIN);
    digitalWrite(PIN_SDA, HIGH);
    digitalWrite(PIN_SCL, HIGH);

    for (int i = 0; i < 9; i++) {
        digitalWrite(PIN_SCL, LOW);  delayMicroseconds(10);
        digitalWrite(PIN_SCL, HIGH); delayMicroseconds(10);
        if (digitalRead(PIN_SDA)) break;
    }
    digitalWrite(PIN_SDA, LOW);  delayMicroseconds(10);
    digitalWrite(PIN_SCL, HIGH); delayMicroseconds(10);
    digitalWrite(PIN_SDA, HIGH); delayMicroseconds(10);

#if USE_EXPANSION_BOARD
    Wire.begin();
#else
    Wire.begin(I2C_SDA, I2C_SCL);
#endif
    delay(30);
    if (Serial) Serial.println("[I2C] bus recovery done");
}

// ── I2C scan ──────────────────────────────────────────────────
static void i2c_scan() {
    if (!Serial) return;
    Serial.println("[I2C] Scanning 0x01-0x7F ...");
    uint8_t found = 0;
    for (uint8_t addr = 1; addr < 128; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            Serial.printf("[I2C]   device at 0x%02X\n", addr);
            found++;
        }
    }
    if (found == 0) Serial.println("[I2C]   no devices found");
    else            Serial.printf("[I2C] %d device(s) found\n", found);
}

// ── Accelerometer init with retry + recovery ──────────────────
static bool accel_init_robust(int max_tries = 5) {
    for (int n = 1; n <= max_tries; n++) {
        delay(60);
        if (accel_init()) {
            if (Serial) Serial.printf("[ACCEL] ready on try %d\n", n);
            return true;
        }
        if (Serial) Serial.printf("[ACCEL] not found (try %d/%d) — recovering bus\n", n, max_tries);
        i2c_recover();
    }
    if (Serial) Serial.println("[ACCEL] failed after all attempts — check wiring & USE_EXPANSION_BOARD");
    return false;
}

// ─────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) delay(10);

#if USE_EXPANSION_BOARD
    Wire.begin();
    if (Serial) Serial.println("[INFO] I2C: expansion board");
#else
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, INPUT_PULLUP);
    Wire.begin(I2C_SDA, I2C_SCL);
    if (Serial) Serial.printf("[INFO] I2C: direct wiring D%d/D%d\n", I2C_SDA, I2C_SCL);
#endif

    i2c_scan();
    s_accel_ok = accel_init_robust();

    vibration_init();
    ble_set_command_callback([](uint8_t id) { vibration_play(id); });
    ble_init();

    if (s_accel_ok) {
        window_task_start();
        if (Serial) Serial.printf("[INFO] %d Hz sampling, %d s window\n",
                                  SAMPLE_RATE_HZ, WINDOW_DURATION_S);
    }
}

void loop() {
    if (!s_accel_ok) { delay(1000); return; }

    float sum;
    while (window_pop(sum)) {
        if (Serial) Serial.printf("[WINDOW] %.4f g  conn=%d\n", sum, ble_connected());
        ble_send_window(sum);
    }
    ble_keepalive();
    delay(100);
}
