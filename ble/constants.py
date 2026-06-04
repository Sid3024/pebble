# Must match firmware/src/ble/ble.cpp exactly.
SERVICE_UUID      = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
WINDOW_CHAR_UUID  = "a1b2c3d4-e5f6-7890-abcd-ef1234567891"
COMMAND_CHAR_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567892"

PEBBLE_NAME_PREFIX     = "Pebble_"
PEBBLE_LED_NAME_PREFIX = "PebbleLED_"

# LED display MCU UUIDs — must match LEDLight/src/config/led_config.h
LED_SERVICE_UUID = "b1c2d3e4-f5a6-7890-abcd-ef1234567890"
LED_CMD_UUID     = "b1c2d3e4-f5a6-7890-abcd-ef1234567891"

# Vibration pattern IDs — must match firmware/src/vibration/vibration.h exactly.
VIBR_TEAM1      = 1   # 5 s team-1 assignment  (quick triple tap)
VIBR_TEAM2      = 2   # 5 s team-2 assignment  (long-short)
VIBR_MILESTONE1 = 3   # 25 % progress          (two gentle taps)
VIBR_MILESTONE2 = 4   # 50 % progress          (three medium pulses)
VIBR_MILESTONE3 = 5   # 75 % progress          (four quick taps)
VIBR_WIN        = 6   # full bloom / win       (rapid burst + hold)
VIBR_FLOWER_50  = 7   # every 50 flowers grown (happy double-tap + hold)
VIBR_LAST_10    = 8   # last 10 s warning      (5 rapid anxious pulses)
