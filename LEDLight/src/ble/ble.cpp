#include "ble.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include "config/led_config.h"
#include "esp_mac.h"

static led_cmd_cb_t s_cb        = nullptr;
static bool         s_connected = false;

// ── Connection callbacks ──────────────────────────────────────

class ServerCB : public BLEServerCallbacks {
    void onConnect(BLEServer*) override {
        s_connected = true;
        Serial.println("[BLE] hub connected");
    }
    void onDisconnect(BLEServer* srv) override {
        s_connected = false;
        Serial.println("[BLE] hub disconnected — restarting advertising");
        srv->startAdvertising();
    }
};

// ── Command characteristic ────────────────────────────────────

class CmdCB : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* c) override {
        if (!s_cb) return;
        std::string val = c->getValue();
        if (val.size() >= 2) {
            s_cb((uint8_t)val[0], (uint8_t)val[1]);
        }
    }
};

// ── Public API ────────────────────────────────────────────────

void ble_led_set_callback(led_cmd_cb_t cb) { s_cb = cb; }

void ble_led_init() {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BT);
    char name[24];
    snprintf(name, sizeof(name), "PebbleLED_%02X%02X%02X", mac[3], mac[4], mac[5]);

    BLEDevice::init(name);

    BLEServer*  server  = BLEDevice::createServer();
    server->setCallbacks(new ServerCB());

    BLEService* service = server->createService(LED_SERVICE_UUID);

    // Write-with-response + write-no-response for fast 10 Hz updates
    BLECharacteristic* cmd = service->createCharacteristic(
        LED_CMD_UUID,
        BLECharacteristic::PROPERTY_WRITE |
        BLECharacteristic::PROPERTY_WRITE_NR
    );
    cmd->setCallbacks(new CmdCB());

    service->start();

    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(LED_SERVICE_UUID);
    adv->setScanResponse(true);
    BLEDevice::startAdvertising();

    Serial.printf("[BLE] advertising as %s\n", name);
}

bool ble_led_connected() { return s_connected; }
