#include "ble.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "esp_mac.h"
#include <constants.h>   // SERVICE_UUID, WINDOW_CHAR_UUID, COMMAND_CHAR_UUID

static BLECharacteristic* s_window_char = nullptr;
static bool               s_connected   = false;
static ble_command_cb_t   s_command_cb  = nullptr;

class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer*) override {
        s_connected = true;
        Serial.println("[BLE] client connected");
    }
    void onDisconnect(BLEServer* server) override {
        s_connected = false;
        Serial.println("[BLE] client disconnected — restarting advertising");
        server->startAdvertising();
    }
};

class CommandCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* c) override {
        if (!s_command_cb) return;
        std::string val = c->getValue();
        if (val.size() >= 1) {
            Serial.printf("[BLE] command 0x%02X\n", (uint8_t)val[0]);
            s_command_cb((uint8_t)val[0]);
        }
    }
};

void ble_set_command_callback(ble_command_cb_t cb) { s_command_cb = cb; }

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
    BLEDevice::getAdvertising()->addServiceUUID(SERVICE_UUID);
    BLEDevice::getAdvertising()->setScanResponse(true);
    BLEDevice::startAdvertising();

    Serial.printf("[BLE] advertising as %s\n", name);
}

void ble_send_window(float window_sum) {
    if (!s_connected || !s_window_char) return;
    s_window_char->setValue(reinterpret_cast<uint8_t*>(&window_sum), sizeof(float));
    s_window_char->notify();
}

bool ble_connected() { return s_connected; }
