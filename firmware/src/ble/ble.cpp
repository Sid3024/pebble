/*
 * ble.cpp — BLE GATT Server Implementation
 *
 * Sets up the ESP32 as a BLE peripheral advertising as "Pebble_XXXXXX".
 * Creates one GATT service with two characteristics:
 *   - Window characteristic (notify): ble_send_window() packs an ImuWindow
 *     into a 20-byte struct and notifies the connected central.
 *   - Command characteristic (write-no-response): incoming bytes are
 *     dispatched to a callback (used for vibration pattern IDs).
 *
 * ServerCallbacks auto-restarts advertising on disconnect so the pod
 * is always discoverable when not connected.
 */

#include "ble.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <math.h>
#include "esp_mac.h"
#include "window/window.h"

#define SERVICE_UUID      "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
#define WINDOW_CHAR_UUID  "a1b2c3d4-e5f6-7890-abcd-ef1234567891"
#define COMMAND_CHAR_UUID "a1b2c3d4-e5f6-7890-abcd-ef1234567892"

static BLECharacteristic* s_window_char = nullptr;
static bool               s_connected   = false;
static ble_command_cb_t   s_command_cb  = nullptr;

struct PackedImuWindow {
    uint8_t magic;
    uint8_t version;
    uint16_t activity_milli;
    int16_t ax_mg;
    int16_t ay_mg;
    int16_t az_mg;
    int16_t gx_cdeg;
    int16_t gy_cdeg;
    int16_t gz_cdeg;
    int16_t roll_cdeg;
    int16_t pitch_cdeg;
} __attribute__((packed));

static int16_t clamp_i16(float value) {
    if (value > 32767.0f) return 32767;
    if (value < -32768.0f) return -32768;
    return static_cast<int16_t>(lroundf(value));
}

class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer*) override {
        s_connected = true;
        Serial.println("[BLE] client connected");
    }
    void onDisconnect(BLEServer* server) override {
        s_connected = false;
        Serial.println("[BLE] client disconnected - restarting advertising");
        server->startAdvertising();
    }
};

class CommandCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* c) override {
        if (!s_command_cb) return;
        std::string val = c->getValue();
        if (val.size() >= 1) {
            Serial.printf("[BLE] command 0x%02X received\n", (uint8_t)val[0]);
            s_command_cb((uint8_t)val[0]);
        }
    }
};

void ble_set_command_callback(ble_command_cb_t cb) {
    s_command_cb = cb;
}

void ble_init() {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BT);
    char name[16];
    snprintf(name, sizeof(name), "Pebble_%02X%02X%02X", mac[3], mac[4], mac[5]);

    BLEDevice::init(name);

    BLEServer*  server  = BLEDevice::createServer();
    server->setCallbacks(new ServerCallbacks());

    BLEService* service = server->createService(SERVICE_UUID);

    s_window_char = service->createCharacteristic(
        WINDOW_CHAR_UUID, BLECharacteristic::PROPERTY_NOTIFY);
    s_window_char->addDescriptor(new BLE2902());

    BLECharacteristic* cmd = service->createCharacteristic(
        COMMAND_CHAR_UUID, BLECharacteristic::PROPERTY_WRITE);
    cmd->setCallbacks(new CommandCallbacks());

    service->start();

    BLEAdvertising* adv = BLEDevice::getAdvertising();
    BLEAdvertisementData adv_data;
    adv_data.setFlags(0x06);
    adv_data.setCompleteServices(BLEUUID(SERVICE_UUID));
    adv_data.setName("Pebble");

    BLEAdvertisementData scan_data;
    scan_data.setName(name);

    adv->setAdvertisementData(adv_data);
    adv->setScanResponseData(scan_data);
    adv->addServiceUUID(SERVICE_UUID);
    adv->setScanResponse(true);
    BLEDevice::startAdvertising();

    Serial.printf("[BLE] advertising as %s\n", name);
}

void ble_send_window(const ImuWindow &window) {
    if (!s_connected || !s_window_char) return;
    PackedImuWindow packet{
        0x50,
        2,
        static_cast<uint16_t>(max(0, min(65535, static_cast<int>(lroundf(window.activity * 1000.0f))))),
        clamp_i16(window.ax * 1000.0f),
        clamp_i16(window.ay * 1000.0f),
        clamp_i16(window.az * 1000.0f),
        clamp_i16(window.gx * 100.0f),
        clamp_i16(window.gy * 100.0f),
        clamp_i16(window.gz * 100.0f),
        clamp_i16(window.roll * 100.0f),
        clamp_i16(window.pitch * 100.0f),
    };
    s_window_char->setValue(reinterpret_cast<uint8_t*>(&packet), sizeof(packet));
    s_window_char->notify();
}

void ble_send_status(uint8_t error_code) {
    if (!s_connected || !s_window_char) return;
    uint8_t pkt[3] = { 0xE1, error_code, 0 };
    s_window_char->setValue(pkt, sizeof(pkt));
    s_window_char->notify();
}

bool ble_connected() {
    return s_connected;
}
