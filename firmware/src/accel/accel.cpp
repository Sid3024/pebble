#include "accel.h"
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <math.h>

static constexpr float G_TO_MS2 = 9.80665f;
static Adafruit_MPU6050 s_mpu;
static uint8_t s_active_addr = 0;
static bool    s_use_raw     = false;

// Sensitivities matching the raw register configuration applied in
// init_raw_mpu6500() below (+-4g accel, +-500 dps gyro).
static constexpr float ACCEL_SENS_4G    = 8192.0f; // LSB per g
static constexpr float GYRO_SENS_500DPS = 65.5f;   // LSB per deg/s

// Reads the WHO_AM_I register (0x75) directly over I2C, bypassing the
// Adafruit driver's strict device-ID check, so we can identify what chip is
// actually on the bus (genuine MPU6050 = 0x68; MPU6500/9250-family = 0x70/0x71/0x73/0x98).
static int read_who_am_i(uint8_t addr) {
    Wire.beginTransmission(addr);
    Wire.write(0x75);
    if (Wire.endTransmission(false) != 0) return -1;
    if (Wire.requestFrom(addr, (uint8_t)1) != 1) return -1;
    return Wire.read();
}

static bool write_reg(uint8_t addr, uint8_t reg, uint8_t value) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.write(value);
    return Wire.endTransmission() == 0;
}

// MPU6500/9250-family chips share the MPU6050 register map for power
// management, filter config, range config, and sensor data output, so we
// can drive them with plain register writes/reads without a dedicated library.
static bool init_raw_mpu6500(uint8_t addr) {
    if (!write_reg(addr, 0x6B, 0x01)) return false; // PWR_MGMT_1: wake up, PLL clock
    delay(50);
    write_reg(addr, 0x1A, 0x03); // CONFIG: ~44 Hz DLPF
    write_reg(addr, 0x1B, 0x08); // GYRO_CONFIG:  +-500 dps
    write_reg(addr, 0x1C, 0x08); // ACCEL_CONFIG: +-4 g
    return true;
}

static bool read_raw_sample(uint8_t addr, ImuSample &sample) {
    Wire.beginTransmission(addr);
    Wire.write(0x3B); // ACCEL_XOUT_H
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(addr, (uint8_t)14) != 14) return false;

    int16_t ax = (Wire.read() << 8) | Wire.read();
    int16_t ay = (Wire.read() << 8) | Wire.read();
    int16_t az = (Wire.read() << 8) | Wire.read();
    Wire.read(); Wire.read(); // temperature, unused
    int16_t gx = (Wire.read() << 8) | Wire.read();
    int16_t gy = (Wire.read() << 8) | Wire.read();
    int16_t gz = (Wire.read() << 8) | Wire.read();

    sample.ax = ax / ACCEL_SENS_4G;
    sample.ay = ay / ACCEL_SENS_4G;
    sample.az = az / ACCEL_SENS_4G;
    sample.gx = gx / GYRO_SENS_500DPS;
    sample.gy = gy / GYRO_SENS_500DPS;
    sample.gz = gz / GYRO_SENS_500DPS;

    sample.roll = atan2f(sample.ay, sample.az) * 180.0f / PI;
    sample.pitch = atan2f(-sample.ax, sqrtf(sample.ay * sample.ay + sample.az * sample.az)) * 180.0f / PI;
    return true;
}

bool imu_init() {
    const uint8_t addresses[] = {IMU_I2C_ADDR, IMU_I2C_ADDR_ALT};
    for (uint8_t addr : addresses) {
        int who_am_i = read_who_am_i(addr);
        if (who_am_i < 0) {
            Serial.printf("[IMU] no response at 0x%02X\n", addr);
            continue;
        }
        Serial.printf("[IMU] device at 0x%02X responds, WHO_AM_I=0x%02X\n", addr, who_am_i);

        if (who_am_i == 0x68 && s_mpu.begin(addr, &Wire)) {
            s_active_addr = addr;
            s_use_raw = false;
            s_mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
            s_mpu.setGyroRange(MPU6050_RANGE_500_DEG);
            s_mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
            Serial.printf("[IMU] MPU6050 ready at 0x%02X\n", s_active_addr);
            return true;
        }

        if ((who_am_i == 0x70 || who_am_i == 0x71 || who_am_i == 0x73 || who_am_i == 0x98)
            && init_raw_mpu6500(addr)) {
            s_active_addr = addr;
            s_use_raw = true;
            Serial.printf("[IMU] MPU6500-compatible chip (WHO_AM_I=0x%02X) ready at 0x%02X (raw driver)\n",
                          who_am_i, addr);
            return true;
        }
    }

    Serial.println("[IMU] no compatible IMU found at 0x68 or 0x69");
    return false;
}

bool imu_read(ImuSample &sample) {
    if (s_use_raw) {
        if (!read_raw_sample(s_active_addr, sample)) {
            Serial.println("[IMU] raw register read failed");
            return false;
        }
        return true;
    }

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
