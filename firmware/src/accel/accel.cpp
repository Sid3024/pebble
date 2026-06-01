#include "accel.h"
#include "LIS3DHTR.h"
#include <Wire.h>

static LIS3DHTR<TwoWire> s_lis;

bool accel_init() {
    s_lis.begin(Wire, ACCEL_I2C_ADDR);
    if (!s_lis) return false;

    s_lis.setOutputDataRate(LIS3DHTR_DATARATE_100HZ);
    s_lis.setHighSolution(true);  // 12-bit resolution
    return true;
}

bool accel_read(float &ax, float &ay, float &az) {
    if (!s_lis.isConnection()) return false;
    s_lis.getAcceleration(&ax, &ay, &az);
    return true;
}
