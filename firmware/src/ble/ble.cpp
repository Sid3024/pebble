#include "ble.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "esp_mac.h"

// Custom 128-bit UUIDs — must match hub/ble/constants.py exactly.
#define SERVICE_UUID     "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
#define WINDOW_CHAR_UUID "a1b2c3d4-e5f6-7890-abcd-ef1234567891"

static BLECharacteristic* s_window_char = nullptr;
static bool               s_connected   = false;

// ── Connection callbacks ───────────────────────────────────────────────────

class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer*) override {
        s_connected = true;
        Serial.println("[BLE] Client connected");
    }
    void onDisconnect(BLEServer* server) override {
        s_connected = false;
        Serial.println("[BLE] Client disconnected — restarting advertising");
        server->startAdvertising();
    }
};

// ── Public API ─────────────────────────────────────────────────────────────

void ble_init() {
    // Build device name from last 3 bytes of Bluetooth MAC for uniqueness.
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BT);
    char name[16];
    snprintf(name, sizeof(name), "Pebble_%02X%02X%02X", mac[3], mac[4], mac[5]);

    BLEDevice::init(name);

    BLEServer* server = BLEDevice::createServer();
    server->setCallbacks(new ServerCallbacks());

    BLEService* service = server->createService(SERVICE_UUID);

    s_window_char = service->createCharacteristic(
        WINDOW_CHAR_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    // BLE2902 is the standard CCCD descriptor; required for notify to work.
    s_window_char->addDescriptor(new BLE2902());

    service->start();

    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(SERVICE_UUID);
    adv->setScanResponse(true);
    BLEDevice::startAdvertising();

    Serial.printf("[BLE] Advertising as %s\n", name);
}

void ble_send_window(float window_sum) {
    if (!s_connected || !s_window_char) return;
    // Send as 4-byte little-endian float.
    s_window_char->setValue(reinterpret_cast<uint8_t*>(&window_sum), sizeof(float));
    s_window_char->notify();
}

bool ble_connected() {
    return s_connected;
}
