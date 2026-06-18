"""
Input handling module for the Volume game.

This file defines how effort data enters the Volume game. It provides two
pluggable "effort sources" -- one that reads real sensor data from a XIAO
ESP32S3 pod over a USB serial connection, and one that generates simulated
effort using a sine wave for development and testing without hardware.

It also contains a flexible line parser (parse_sensor_line) that can interpret
three different serial data formats:
    - JSON objects:      {"ax": 0.1, "ay": 0.2, "az": 1.0}
    - Key=value pairs:   ax=0.1 ay=0.2 az=1.0
    - Raw CSV numbers:   0.1, 0.2, 1.0  (or a single effort value)

This flexibility means the firmware on the XIAO ESP32S3 can use whichever
output format is most convenient, and the Volume game will understand it.

Libraries used:
    - json: for parsing JSON-formatted sensor lines.
    - random: for adding jitter to simulated effort.
    - re: for regex-based key=value parsing.
    - time: for controlling simulation tick rate.
    - dataclasses: for the immutable EffortEvent container.
    - math.sin: for generating the sine-wave simulation.
    - serial (pyserial, optional): for reading from a real serial port.

Classes:
    - EffortEvent: immutable data container for one effort reading plus metadata.
    - EffortSource: abstract base class for effort providers.
    - SerialEffortSource: reads real IMU data from a serial port.
    - SimulatedEffortSource: generates fake effort via a sine wave for testing.

Functions:
    - parse_sensor_line(): multi-format parser for serial data lines.
    - list_serial_ports(): enumerate available serial ports on the machine.
    - _parse_json(), _parse_key_values(), _parse_csv(): private format parsers.

Fits into the Pebble project as the data-ingestion layer of the Volume game,
sitting between the physical pod (or simulator) and the effort calculator in
effort.py.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from math import sin
from typing import Iterator

from .effort import EffortCalculator, ImuReading


@dataclass(frozen=True)
class EffortEvent:
    """Immutable record of one effort reading.

    Attributes:
        effort: the computed effort value (0.0 = no movement, higher = more).
        source: a human-readable label indicating where this reading came from,
                e.g. "serial:imu", "serial:effort", or "simulator".
        raw:    the original text line from the serial port (empty for simulated
                events). Useful for debugging.
    """

    effort: float
    source: str
    raw: str = ""


class EffortSource:
    """Abstract base class for all effort data providers.

    Subclasses must implement events() to yield a (potentially infinite) stream
    of EffortEvent objects. The main loop in app.py iterates over this stream.
    """

    def events(self) -> Iterator[EffortEvent]:
        raise NotImplementedError


def parse_sensor_line(line: str, calculator: EffortCalculator) -> EffortEvent | None:
    """Parse JSON, key=value, or CSV sensor lines into an effort event.

    Tries three formats in order:
        1. JSON: ``{"ax": ..., "ay": ..., "az": ...}`` or ``{"effort": ...}``
        2. Key=value: ``ax=0.1 ay=0.2 az=1.0``
        3. CSV: ``0.1, 0.2, 1.0`` (3 values = accel), single value = effort,
           6+ values = accel + gyro.

    If the parsed data contains an "effort" key, it is used directly. Otherwise,
    if accelerometer axes (ax, ay, az) are present, the calculator converts them
    into a smoothed effort value.

    Returns None if the line is blank or does not match any known format.
    """
    text = line.strip()
    if not text:
        return None

    values = _parse_json(text) or _parse_key_values(text) or _parse_csv(text)
    if not values:
        return None

    if "effort" in values:
        return EffortEvent(float(values["effort"]), "serial:effort", text)

    required = {"ax", "ay", "az"}
    if required.issubset(values):
        reading = ImuReading(
            ax=float(values["ax"]),
            ay=float(values["ay"]),
            az=float(values["az"]),
            gx=float(values.get("gx", 0.0)),
            gy=float(values.get("gy", 0.0)),
            gz=float(values.get("gz", 0.0)),
        )
        return EffortEvent(calculator.update(reading), "serial:imu", text)

    return None


class SerialEffortSource(EffortSource):
    """Read real IMU data from a XIAO ESP32S3 pod connected via USB serial.

    Opens the given serial port at the specified baud rate and continuously reads
    lines. Each line is parsed by parse_sensor_line() and, if valid, yielded as
    an EffortEvent.

    Requires the ``pyserial`` library; raises RuntimeError with an install hint
    if it is missing.
    """

    def __init__(self, port: str, baud: int, calculator: EffortCalculator) -> None:
        self.port = port
        self.baud = baud
        self.calculator = calculator

    def events(self) -> Iterator[EffortEvent]:
        """Yield effort events forever by reading lines from the serial port."""
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError(
                "pyserial is required for --port mode. Install with: python -m pip install -r volume/requirements.txt"
            ) from exc

        with serial.Serial(self.port, self.baud, timeout=1) as ser:
            while True:
                line = ser.readline().decode("utf-8", errors="replace")
                event = parse_sensor_line(line, self.calculator)
                if event is not None:
                    yield event


class SimulatedEffortSource(EffortSource):
    """Generate fake effort data without any hardware.

    Produces a smooth sine-wave effort signal with small random jitter, useful
    for testing the volume-mapping pipeline and UI without connecting a real pod.
    The sine wave oscillates between ~0 and ~1.6, roughly matching the effort
    range expected from real movement.

    Parameters:
        interval_s: seconds to sleep between simulated readings (default 0.1,
                    i.e. ~10 readings per second).
    """

    def __init__(self, interval_s: float = 0.1) -> None:
        self.interval_s = interval_s

    def events(self) -> Iterator[EffortEvent]:
        """Yield simulated effort events at a steady tick rate."""
        step = 0
        while True:
            wave = (sin(step / 12.0) + 1.0) / 2.0
            jitter = random.uniform(-0.04, 0.04)
            effort = max(0.0, wave * 1.6 + jitter)
            yield EffortEvent(effort=effort, source="simulator")
            step += 1
            time.sleep(self.interval_s)


def list_serial_ports() -> list[str]:
    """Return a list of available serial port device names (e.g. ["COM3", "COM4"]).

    Uses pyserial's list_ports utility. Returns an empty list if pyserial is not
    installed, rather than raising an error, because this function is used for
    optional discovery (the --list-ports CLI flag).
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    return [port.device for port in list_ports.comports()]


# ---------------------------------------------------------------------------
# Private format parsers
# ---------------------------------------------------------------------------


def _parse_json(text: str) -> dict[str, float] | None:
    """Try to parse *text* as a JSON object with numeric values.

    Returns a dict with lower-cased keys mapped to floats, or None if the text
    is not valid JSON or is not an object. The leading '{' check is a fast-path
    to avoid calling json.loads on obviously non-JSON lines.
    """
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return {str(key).lower(): float(value) for key, value in payload.items()}


def _parse_key_values(text: str) -> dict[str, float] | None:
    """Try to parse *text* as space-separated key=value or key:value pairs.

    Uses a regex to find all ``name = number`` or ``name: number`` patterns
    in the line. Returns None if no matches are found.
    """
    matches = re.findall(r"([A-Za-z_]+)\s*[:=]\s*(-?\d+(?:\.\d+)?)", text)
    if not matches:
        return None
    return {key.lower(): float(value) for key, value in matches}


def _parse_csv(text: str) -> dict[str, float] | None:
    """Try to parse *text* as comma-separated numbers.

    Interprets the values positionally:
        - 1 number  -> {"effort": value}
        - 3 numbers -> {"ax", "ay", "az"} (accelerometer only)
        - 6+ numbers -> {"ax", "ay", "az", "gx", "gy", "gz"} (accel + gyro)

    Returns None if any token is not a valid float or if the count does not
    match a recognised format (e.g. 2, 4, or 5 numbers).
    """
    try:
        numbers = [float(part.strip()) for part in text.split(",")]
    except ValueError:
        return None

    if len(numbers) == 1:
        return {"effort": numbers[0]}
    if len(numbers) == 3:
        return {"ax": numbers[0], "ay": numbers[1], "az": numbers[2]}
    if len(numbers) >= 6:
        return {
            "ax": numbers[0],
            "ay": numbers[1],
            "az": numbers[2],
            "gx": numbers[3],
            "gy": numbers[4],
            "gz": numbers[5],
        }
    return None
