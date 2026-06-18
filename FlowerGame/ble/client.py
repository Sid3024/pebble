"""
FlowerGame-specific BLE client re-export.

This module re-exports PebbleClient from the shared ``ble`` package at the
project root.  It exists so that FlowerGame code can import PebbleClient
with a package-relative path:

    from FlowerGame.ble.client import PebbleClient

The actual connection management, GATT notification handling, and vibration
command writing all live in ble/client.py (the shared library).
"""

from ble.client import PebbleClient

__all__ = ["PebbleClient"]
