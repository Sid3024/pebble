"""
BLE constants shared between the Python backend and the C++/Arduino firmware.

This file defines:
    1. BLE service and characteristic UUIDs for the IMU sensor pods.
    2. BLE service and characteristic UUIDs for the LED display MCU.
    3. BLE advertising name prefixes used to identify Pebble devices during scanning.
    4. Vibration pattern IDs sent as commands to pods to trigger haptic feedback.

CRITICAL: These values are duplicated in firmware source code.  If you change
a UUID or pattern ID here you MUST update the corresponding firmware header
(paths noted in comments) or the BLE link will silently fail.

How it fits into Pebble:
    - scanner.py uses the name prefixes to filter discovered BLE devices.
    - client.py uses the service/characteristic UUIDs to subscribe to IMU
      notifications and write vibration commands.
    - Game controllers (FlowerController, CompetitiveFlowerController) import
      the VIBR_* constants to queue haptic feedback at game milestones.
"""

# ── IMU sensor pod UUIDs ──────────────────────────────────────────────────────
# Must match firmware/src/ble/ble.cpp exactly.
# SERVICE_UUID        : The primary GATT service exposed by each Pebble pod.
# WINDOW_CHAR_UUID    : Characteristic that the pod uses to NOTIFY the backend
#                       with a 4-byte little-endian float (the "window sum")
#                       every ~250 ms firmware window period.
# COMMAND_CHAR_UUID   : Characteristic the backend WRITES to in order to send
#                       a 1-byte vibration pattern ID back to the pod.
SERVICE_UUID      = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
WINDOW_CHAR_UUID  = "a1b2c3d4-e5f6-7890-abcd-ef1234567891"
COMMAND_CHAR_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567892"

# ── BLE advertising name prefixes ─────────────────────────────────────────────
# Every sensor pod advertises as "Pebble_<id>"; the LED display as "PebbleLED_<id>".
# The scanner module filters on these prefixes to find relevant devices.
PEBBLE_NAME_PREFIX     = "Pebble_"
PEBBLE_LED_NAME_PREFIX = "PebbleLED_"

# ── LED display MCU UUIDs ─────────────────────────────────────────────────────
# Must match LEDLight/src/config/led_config.h.
# LED_SERVICE_UUID : GATT service on the LED display MCU.
# LED_CMD_UUID     : Characteristic to WRITE LED commands (color, pattern, etc.).
LED_SERVICE_UUID = "b1c2d3e4-f5a6-7890-abcd-ef1234567890"
LED_CMD_UUID     = "b1c2d3e4-f5a6-7890-abcd-ef1234567891"

# ── Vibration pattern IDs ─────────────────────────────────────────────────────
# Must match firmware/src/vibration/vibration.h exactly.
# Each ID maps to a pre-programmed vibration sequence on the pod's motor.
# The backend writes a single byte (the pattern ID) to COMMAND_CHAR_UUID.
VIBR_TEAM1      = 1   # 5 s team-1 assignment  (quick triple tap)
VIBR_TEAM2      = 2   # 5 s team-2 assignment  (long-short)
VIBR_MILESTONE1 = 3   # 25 % progress          (two gentle taps)
VIBR_MILESTONE2 = 4   # 50 % progress          (three medium pulses)
VIBR_MILESTONE3 = 5   # 75 % progress          (four quick taps)
VIBR_WIN        = 6   # full bloom / win       (rapid burst + hold)
VIBR_FLOWER_50  = 7   # every 50 flowers grown (happy double-tap + hold)
VIBR_LAST_10    = 8   # last 10 s warning      (5 rapid anxious pulses)
