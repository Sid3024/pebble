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
    effort: float
    source: str
    raw: str = ""


class EffortSource:
    def events(self) -> Iterator[EffortEvent]:
        raise NotImplementedError


def parse_sensor_line(line: str, calculator: EffortCalculator) -> EffortEvent | None:
    """Parse JSON, key=value, or CSV sensor lines into an effort event."""
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
    def __init__(self, port: str, baud: int, calculator: EffortCalculator) -> None:
        self.port = port
        self.baud = baud
        self.calculator = calculator

    def events(self) -> Iterator[EffortEvent]:
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
    def __init__(self, interval_s: float = 0.1) -> None:
        self.interval_s = interval_s

    def events(self) -> Iterator[EffortEvent]:
        step = 0
        while True:
            wave = (sin(step / 12.0) + 1.0) / 2.0
            jitter = random.uniform(-0.04, 0.04)
            effort = max(0.0, wave * 1.6 + jitter)
            yield EffortEvent(effort=effort, source="simulator")
            step += 1
            time.sleep(self.interval_s)


def list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    return [port.device for port in list_ports.comports()]


def _parse_json(text: str) -> dict[str, float] | None:
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
    matches = re.findall(r"([A-Za-z_]+)\s*[:=]\s*(-?\d+(?:\.\d+)?)", text)
    if not matches:
        return None
    return {key.lower(): float(value) for key, value in matches}


def _parse_csv(text: str) -> dict[str, float] | None:
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
