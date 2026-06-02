#pragma once

// ================================================================
// Shared protocol constants
// Must match Python ble/constants.py exactly.
// ================================================================

// ── BLE UUIDs (game pods) ─────────────────────────────────────
#define SERVICE_UUID        "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
#define WINDOW_CHAR_UUID    "a1b2c3d4-e5f6-7890-abcd-ef1234567891"
#define COMMAND_CHAR_UUID   "a1b2c3d4-e5f6-7890-abcd-ef1234567892"

// ── Device naming ─────────────────────────────────────────────
#define PEBBLE_NAME_PREFIX  "Pebble_"

// ── Vibration pattern IDs ─────────────────────────────────────
// Command byte written to COMMAND_CHAR to trigger a pattern.
#define VIBR_TEAM1      1   // 5 s — team 1 assignment  (quick triple tap)
#define VIBR_TEAM2      2   // 5 s — team 2 assignment  (long-short)
#define VIBR_MILESTONE1 3   // ~0.4 s — 25 % time elapsed
#define VIBR_MILESTONE2 4   // ~1.2 s — 50 % time elapsed
#define VIBR_MILESTONE3 5   // ~1.2 s — 75 % time elapsed
#define VIBR_WIN        6   // ~1.7 s — game over / win
#define VIBR_FLOWER_50  7   // ~0.7 s — every 50 flowers grown
