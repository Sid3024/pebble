#include "accel.h"
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <math.h>

static constexpr float G_TO_MS2 = 9.80665f;
static Adafruit_MPU6050 s_mpu;
static uint8_t s_active_addr = 0;

bool imu_init() {
    const uint8_t addresses[] = {IMU_I2C_ADDR, IMU_I2C_ADDR_ALT};
    for (uint8_t addr : addresses) {
        Serial.printf("[IMU] trying MPU6050 at 0x%02X...\n", addr);
        if (!s_mpu.begin(addr, &Wire)) {
            continue;
        }

        s_active_addr = addr;
        s_mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
        s_mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        s_mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
        Serial.printf("[IMU] MPU6050 ready at 0x%02X\n", s_active_addr);
        return true;
    }

    Serial.println("[IMU] MPU6050 not found at 0x68 or 0x69");
    return false;
}

bool imu_read(ImuSample &sample) {
    sensors_event_t accel;
    sensors_event_t gyro;
    sensors_event_t temp;

    if (!s_mpu.getEvent(&accel, &gyro, &temp)) {
        Serial.println("[IMU] MPU6050 getEvent failed");
        return false;
    }

    sample.ax = accel.acceleration.x / G_TO_MS2;
    sample.ay = accel.acceleration.y / G_TO_MS2;
    sample.az = accel.acceleration.z / G_TO_MS2;
    sample.gx = gyro.gyro.x * 180.0f / PI;
    sample.gy = gyro.gyro.y * 180.0f / PI;
    sample.gz = gyro.gyro.z * 180.0f / PI;

    sample.roll = atan2f(sample.ay, sample.az) * 180.0f / PI;
    sample.pitch = atan2f(-sample.ax, sqrtf(sample.ay * sample.ay + sample.az * sample.az)) * 180.0f / PI;
    return true;
}
