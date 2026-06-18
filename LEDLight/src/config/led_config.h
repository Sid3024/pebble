/**
 * ============================================================================
 * LEDLight/src/config/led_config.h — LED Strip Hardware & BLE Configuration
 * ============================================================================
 *
 * PURPOSE:
 *   Central configuration file for the Pebble LED Light module. Contains
 *   all hardware-specific constants and tuning parameters. This is the
 *   ONLY file you need to edit when setting up a new LED controller
 *   with different hardware.
 *
 * HOW IT WORKS:
 *   All values are compile-time #define constants. They are consumed by:
 *     - led.cpp: LED strip pin, count, brightness, team colors, animation speed
 *     - ble.cpp: BLE service and characteristic UUIDs
 *
 * SECTIONS:
 *   1. LED strip hardware — pin assignment, LED count, brightness limit
 *   2. Team colors — RGB values for the two competing teams
 *   3. Animation tuning — smoothing factor and blink speed
 *   4. BLE UUIDs — service and characteristic identifiers
 *
 * IMPORTANT:
 *   The BLE UUIDs MUST match the values used in the Python hub's
 *   LEDLight/client.py script. If you change them here, update the
 *   Python side as well, or the hub will not be able to find/control
 *   this LED controller.
 *
 * RELATIONSHIP TO PEBBLE PROJECT:
 *   This file is shared across the LED and BLE subsystems, acting as
 *   the single source of truth for hardware configuration. The team
 *   colors here should visually match what the GameDashboard shows
 *   on screen (Team 1 = blue, Team 2 = orange).
 * ============================================================================
 */

#pragma once

// ================================================================
// LED display configuration — edit this file to match your hardware
// ================================================================

// ── LED strip hardware ──────────────────────────────────────
// NUM_LEDS: Total number of individually addressable LEDs in the WS2812B strip.
//   Adjust this to match your physical strip length.
#define NUM_LEDS        30

// LED_DATA_PIN: The GPIO pin on the XIAO ESP32S3 connected to the strip's
//   data input (DIN). D1 is a convenient choice on the XIAO form factor.
#define LED_DATA_PIN    D1

// LED_BRIGHTNESS: Global brightness limit (0 = off, 255 = maximum).
//   Keep this under 150 to avoid overcurrent when powering the strip
//   from the ESP32's USB power supply. Higher values may cause voltage
//   drops, flickering, or brownouts. 80 is a good balance of visibility
//   and power safety for a 30-LED strip.
#define LED_BRIGHTNESS  80

// ── Team colours (R, G, B) ───────────────────────────────────
// RGB color components for each team's LED color.
// These should visually match the team colors on the GameDashboard:
//   Team 0 (Team 1 on screen) = blue
//   Team 1 (Team 2 on screen) = orange

#define TEAM0_R   0       // Team 1 red component
#define TEAM0_G  80       // Team 1 green component
#define TEAM0_B  255      // Team 1 blue component — blue team

#define TEAM1_R  255      // Team 2 red component
#define TEAM1_G   80      // Team 2 green component
#define TEAM1_B    0      // Team 2 blue component — orange team

// ── Animation tuning ────────────────────────────────────────
// BOUNDARY_SMOOTH: Controls how quickly the color boundary moves when
//   the score ratio changes. This is a lerp factor applied each frame:
//     new_boundary = old_boundary + (target - old_boundary) * BOUNDARY_SMOOTH
//   Range: 0.0 to 1.0
//     0.01 = very slow, dramatic push (takes many frames to settle)
//     0.06 = moderate, smooth push-pull effect (default)
//     0.5  = snappy, almost instant response
//     1.0  = instant jump (no smoothing)
#define BOUNDARY_SMOOTH   0.06f

// CELEBRATE_BLINK_MS: Time in milliseconds for each half of the
//   celebration blink cycle. At 350ms, the full blink cycle is 700ms
//   (on for 350ms, off for 350ms). Used when a team wins or when
//   there's a tie.
#define CELEBRATE_BLINK_MS  350

// ── BLE UUIDs ───────────────────────────────────────────────
// These UUIDs identify the BLE service and characteristic used for
// communication between the Python hub and this LED controller.
// CRITICAL: Must match LEDLight/client.py exactly. If you change
// these, update the Python client as well.
//
// LED_SERVICE_UUID: The BLE service that groups LED-related characteristics.
//   Included in advertising packets so the hub can filter during scanning.
#define LED_SERVICE_UUID  "b1c2d3e4-f5a6-7890-abcd-ef1234567890"

// LED_CMD_UUID: The writable characteristic within the service.
//   The hub writes 2-byte commands (ratio + phase) to this UUID.
#define LED_CMD_UUID      "b1c2d3e4-f5a6-7890-abcd-ef1234567891"
