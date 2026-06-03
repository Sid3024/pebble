#include "accel.h"
#include "LIS3DHTR.h"
#include <Wire.h>

static LIS3DHTR<TwoWire> s_lis;

// Try both common LIS3DHTR addresses at runtime so no recompile is needed
// when swapping between the expansion board (SA0=VCC → 0x19) and direct
// wiring (SA0=GND → 0x18).
static const uint8_t CANDIDATE_ADDRS[] = { 0x19, 0x18 };

bool accel_init() {
    for (uint8_t addr : CANDIDATE_ADDRS) {
        s_lis.begin(Wire, addr);
        if (s_lis) {
            s_lis.setOutputDataRate(LIS3DHTR_DATARATE_100HZ);
            s_lis.setHighSolution(true);   // 12-bit resolution
            Serial.printf("[ACCEL] LIS3DHTR found at 0x%02X\n", addr);
            return true;
        }
    }
    return false;
}

bool accel_read(float &ax, float &ay, float &az) {
    if (!s_lis.isConnection()) {
        Serial.println("[ACCEL] isConnection() false — read skipped");
        return false;
    }
    s_lis.getAcceleration(&ax, &ay, &az);
    return true;
}
