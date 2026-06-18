"""
Entry point script for the Volume game.

This file serves as the top-level runner for the Volume game, an earlier/alternative
game mode in the Pebble project where physical movement of XIAO ESP32S3 IMU pods
controls the system audio volume. It simply delegates to the main() function defined
in the volume_game.app module.

Run this script directly (``python run_volume_game.py``) or via
``python -m volume_game`` to start the game. The main() function handles all CLI
argument parsing and the core event loop.

Libraries used:
    - volume_game.app: internal module containing the main application logic.

Functions / entry points:
    - Imports and calls ``main()`` from volume_game.app.

Fits into the Pebble project as the user-facing launch point for the Volume game,
which is separate from the FlowerGame but shares the same BLE-connected IMU pods.
"""

from volume_game.app import main


if __name__ == "__main__":
    raise SystemExit(main())
