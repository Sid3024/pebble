#include "ble.h"
#include <bluefruit.h>       // Bluefruit52 — bundled with nordicnrf52 platform
#include <constants.h>       // SERVICE_UUID, WINDOW_CHAR_UUID, COMMAND_CHAR_UUID

// No FreeRTOS polling task needed — the SoftDevice handles BLE events via
// hardware interrupts, so BLE and FreeRTOS coexist without explicit polling.

static BLEService        s_service(SERVICE_UUID);
static BLECharacteristic s_window_char(WINDOW_CHAR_UUID);  // notify → hub
static BLECharacteristic s_cmd_char(COMMAND_CHAR_UUID);    // write ← hub

static volatile bool    s_connected  = false;
static ble_command_cb_t s_command_cb = nullptr;

// ── Callbacks ─────────────────────────────────────────────────

static void on_connect(uint16_t conn_handle) {
    s_connected = true;
    BLEConnection* conn = Bluefruit.Connection(conn_handle);
    char peer[32] = {};
    conn->getPeerName(peer, sizeof(peer));
    Serial.printf("[BLE] connected to %s\n", *peer ? peer : "hub");
}

static void on_disconnect(uint16_t conn_handle, uint8_t reason) {
    s_connected = false;
    Serial.printf("[BLE] disconnected (0x%02X) — re-advertising\n", reason);
    Bluefruit.Advertising.start(0);
}

static void on_cmd_written(uint16_t conn_handle, BLECharacteristic* chr,
                           uint8_t* data, uint16_t len) {
    if (!s_command_cb || len < 1) return;
    Serial.printf("[BLE] command 0x%02X\n", data[0]);
    s_command_cb(data[0]);
}

// ── Public API ────────────────────────────────────────────────

void ble_set_command_callback(ble_command_cb_t cb) { s_command_cb = cb; }

void ble_init() {
    Bluefruit.begin();
    Bluefruit.setTxPower(4);   // +4 dBm — maximum TX power for best range

    // Build unique device name from chip factory ID (no MAC read API needed)
    char name[16];
    uint32_t uid = (NRF_FICR->DEVICEID[0] ^ NRF_FICR->DEVICEID[1]) & 0xFFFFFF;
    snprintf(name, sizeof(name), "Pebble_%06lX", uid);
    Bluefruit.setName(name);

    Bluefruit.setConnectCallback(on_connect);
    Bluefruit.setDisconnectCallback(on_disconnect);

    // ── Service + characteristics ─────────────────────────────
    s_service.begin();   // must begin before characteristics

    // Window notify (MCU → hub): 4-byte LE float
    s_window_char.setProperties(CHR_PROPS_NOTIFY | CHR_PROPS_READ);
    s_window_char.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    s_window_char.setFixedLen(sizeof(float));
    s_window_char.begin();

    // Command write (hub → MCU): 1 byte vibration pattern ID
    s_cmd_char.setProperties(CHR_PROPS_WRITE | CHR_PROPS_WRITE_WO_RESP);
    s_cmd_char.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN);
    s_cmd_char.setFixedLen(1);
    s_cmd_char.setWriteCallback(on_cmd_written);
    s_cmd_char.begin();

    // ── Advertising ───────────────────────────────────────────
    Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
    Bluefruit.Advertising.addTxPower();
    Bluefruit.Advertising.addService(s_service);
    Bluefruit.Advertising.setScanResponse(true);
    Bluefruit.Advertising.setFastTimeout(30);
    Bluefruit.Advertising.start(0);   // 0 = advertise indefinitely

    Serial.printf("[BLE] advertising as %s\n", name);
}

void ble_send_window(float window_sum) {
    if (!s_connected) return;
    // notify() returns false if the central has not subscribed yet — safe to ignore
    s_window_char.notify(reinterpret_cast<const uint8_t*>(&window_sum), sizeof(float));
}

bool ble_connected() { return s_connected; }
