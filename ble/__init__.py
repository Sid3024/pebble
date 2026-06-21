"""
ble -- Shared BLE (Bluetooth Low Energy) communication library for the Pebble project.

This package provides the low-level BLE primitives used by all Pebble game modes
(FlowerGame, EffortGame, etc.) to communicate with the physical sensor pods and
the LED display MCU.

What it contains:
    - constants.py : BLE service/characteristic UUIDs and vibration pattern IDs
                     that must stay in sync with the C++ firmware.
    - scanner.py   : Async helpers to discover Pebble pods and LED displays
                     via BLE advertising name prefixes.
    - client.py    : PebbleClient class that manages a persistent BLE connection
                     to one pod -- subscribes to IMU window notifications, forwards
                     them to the game controller, and writes vibration commands back.

Dependencies:
    - bleak : Cross-platform BLE library (async, built on platform-native APIs).

How it fits into Pebble:
    Game backends (e.g. FlowerGame.main) use scanner.scan_for_pebbles() to discover
    pods, then create one PebbleClient per pod.  Each PebbleClient runs an asyncio
    task that listens for window-sum notifications and relays them to the game
    controller's process_window() method.  The controller can queue vibration
    commands, which the client polls and writes back to the pod every second.
"""
