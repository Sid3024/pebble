"""
Volume game package -- map IMU effort from the XIAO ESP32S3 to music volume.

This package implements the Volume game, an earlier/alternative game mode in the
Pebble project. The core idea: physical movement of a XIAO ESP32S3 pod (measured
by its accelerometer and gyroscope) is converted into an "effort" score, which is
then mapped to the computer's system audio volume. Move more, music gets louder.

Package structure:
    - effort.py:  IMU reading dataclass, effort calculation with EMA smoothing,
                  and effort-to-volume mapping.
    - inputs.py:  Pluggable effort sources -- serial port (real hardware) and a
                  sine-wave simulator for development without a pod.
    - volume.py:  Volume backend abstraction -- Windows system volume via pycaw,
                  console dry-run fallback, and a rate-limiter to prevent flooding.
    - app.py:     CLI argument parsing and the main event loop that wires
                  inputs -> effort -> volume together.

This package is part of the broader Pebble project, which centres around XIAO
ESP32S3 pods with IMU sensors. The same BLE pods are used in the FlowerGame.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
