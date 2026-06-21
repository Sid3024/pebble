/**
 * ============================================================================
 * LEDLight/src/ble/ble.cpp — BLE Peripheral Implementation for LED Controller
 * ============================================================================
 *
 * PURPOSE:
 *   Implements the BLE (Bluetooth Low Energy) peripheral that allows the
 *   Python hub to send game state commands to the LED strip controller.
 *   The ESP32S3 acts as a BLE server (peripheral), and the Python hub
 *   acts as a BLE client (central) that discovers, connects, and writes
 *   2-byte commands to control the LED animation.
 *
 * HOW IT WORKS:
 *   1. On initialization (ble_led_init):
 *      - Reads the ESP32's Bluetooth MAC address to generate a unique
 *        device name: "PebbleLED_XXYYZZ" (last 3 bytes of MAC in hex).
 *      - Creates a BLE server with connection/disconnection callbacks.
 *      - Creates a BLE service using the UUID from led_config.h.
 *      - Creates a writable characteristic (also from led_config.h) that
 *        accepts both write-with-response and write-no-response operations.
 *        Write-no-response (WRITE_NR) is important for 10Hz update rate —
 *        it avoids the round-trip acknowledgment overhead of normal writes.
 *      - Starts advertising the service UUID so the hub can discover it.
 *
 *   2. On BLE connection (ServerCB::onConnect):
 *      - Sets the connected flag to true and logs the event.
 *
 *   3. On BLE disconnection (ServerCB::onDisconnect):
 *      - Sets the connected flag to false and immediately restarts
 *        advertising so the hub can reconnect without a reboot.
 *
 *   4. On characteristic write (CmdCB::onWrite):
 *      - Extracts the 2-byte payload from the written value.
 *      - Calls the registered callback with ratio (byte 0) and phase (byte 1).
 *      - The callback (set in main.cpp) forwards these to led_update().
 *
 * LIBRARIES:
 *   - BLEDevice.h, BLEServer.h, BLEUtils.h — ESP32 Arduino BLE library
 *     for creating BLE servers, services, and characteristics.
 *   - esp_mac.h — ESP-IDF API to read the hardware MAC address.
 *   - config/led_config.h — BLE service and characteristic UUIDs.
 *
 * DESIGN DECISIONS:
 *   - The characteristic supports both PROPERTY_WRITE and PROPERTY_WRITE_NR.
 *     The hub uses write-no-response for speed during gameplay (~100ms per
 *     update) and can fall back to write-with-response for reliability.
 *   - Auto-restart advertising on disconnect ensures the hub can always
 *     reconnect without requiring a physical reset of the LED controller.
 *   - The callback pattern (led_cmd_cb_t) decouples BLE from LED logic,
 *     allowing either subsystem to be replaced independently.
 *
 * RELATIONSHIP TO PEBBLE PROJECT:
 *   The Python hub (LEDLight/client.py) scans for devices advertising the
 *   LED_SERVICE_UUID, connects, and writes game state updates. The UUIDs
 *   must match exactly between this firmware and the Python client.
 * ============================================================================
 */

#include "ble.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include "config/led_config.h"
#include "esp_mac.h"

/* Module-level state: callback function pointer and connection flag.
   These are accessed from BLE stack callbacks running on the BLE task. */
static led_cmd_cb_t s_cb        = nullptr;   // Registered command callback
static bool         s_connected = false;     // Hub connection status

// ── Connection callbacks ──────────────────────────────────────
/**
 * BLE Server connection event handler.
 *
 * onConnect: Called by the ESP32 BLE stack when a central device (the Python hub)
 *   establishes a connection. Sets the connected flag and logs the event.
 *
 * onDisconnect: Called when the hub disconnects (intentionally or due to range).
 *   Clears the connected flag and immediately restarts BLE advertising so the
 *   hub can reconnect without needing to reboot the ESP32. This is critical for
 *   robustness — if the hub crashes and restarts, it should be able to find
 *   the LED controller again automatically.
 */
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

// ── Command characteristic callback ──────────────────────────
/**
 * BLE Characteristic write handler.
 *
 * Called by the ESP32 BLE stack whenever the hub writes to the command
 * characteristic. Extracts the 2-byte payload and forwards it to the
 * registered callback (which ultimately calls led_update).
 *
 * Protocol:
 *   - Ignores writes if no callback is registered (safety guard).
 *   - Ignores writes shorter than 2 bytes (malformed commands).
 *   - byte[0] = ratio: 0 (all Team 2) to 255 (all Team 1)
 *   - byte[1] = phase: PHASE_PLAYING(0), PHASE_TEAM0_WIN(1),
 *               PHASE_TEAM1_WIN(2), PHASE_TIE(3), PHASE_WAITING(4)
 */
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

/**
 * Store the callback function that will receive decoded BLE commands.
 * Must be called before ble_led_init() to avoid missing early commands.
 */
void ble_led_set_callback(led_cmd_cb_t cb) { s_cb = cb; }

/**
 * Initialize the complete BLE peripheral stack.
 *
 * Steps:
 *   1. Read the ESP32's Bluetooth MAC address and build a unique device
 *      name using the last 3 bytes (e.g., "PebbleLED_A1B2C3").
 *   2. Initialize the BLE device with this name.
 *   3. Create a BLE server and register connection callbacks.
 *   4. Create a BLE service with the UUID from led_config.h.
 *   5. Create a writable characteristic within the service:
 *      - PROPERTY_WRITE: standard write-with-response (reliable)
 *      - PROPERTY_WRITE_NR: write-no-response (fast, for 10Hz updates)
 *   6. Register the characteristic write callback (CmdCB).
 *   7. Start the service.
 *   8. Configure and start BLE advertising with the service UUID
 *      included in the advertisement packet (so the hub can filter by UUID
 *      during scanning). Scan response is enabled for additional data.
 */
void ble_led_init() {
    // Build unique device name from Bluetooth MAC address
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BT);
    char name[24];
    snprintf(name, sizeof(name), "PebbleLED_%02X%02X%02X", mac[3], mac[4], mac[5]);

    BLEDevice::init(name);

    // Create BLE server with connection lifecycle callbacks
    BLEServer*  server  = BLEDevice::createServer();
    server->setCallbacks(new ServerCB());

    // Create service with the shared UUID (must match Python client)
    BLEService* service = server->createService(LED_SERVICE_UUID);

    // Create the command characteristic — supports both write modes:
    // WRITE (acknowledged) for reliability + WRITE_NR (unacknowledged) for speed
    BLECharacteristic* cmd = service->createCharacteristic(
        LED_CMD_UUID,
        BLECharacteristic::PROPERTY_WRITE |
        BLECharacteristic::PROPERTY_WRITE_NR
    );
    cmd->setCallbacks(new CmdCB());

    service->start();

    // Configure advertising: include the service UUID so the hub can
    // filter during BLE scanning, and enable scan response for extra data
    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(LED_SERVICE_UUID);
    adv->setScanResponse(true);
    BLEDevice::startAdvertising();

    Serial.printf("[BLE] advertising as %s\n", name);
}

/**
 * Check whether the Python hub is currently connected.
 * @returns true if connected, false if disconnected or never connected.
 */
bool ble_led_connected() { return s_connected; }
