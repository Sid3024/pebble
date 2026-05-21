from __future__ import annotations

from importlib import import_module
import queue
import sys
import threading
import time
from dataclasses import dataclass


class SystemVolumeUnavailable(RuntimeError):
    """Raised when the computer's system-volume backend cannot be started."""


def clamp_percent(percent: int) -> int:
    return max(0, min(100, int(percent)))


class VolumeBackend:
    name = "base"

    def set_volume(self, percent: int) -> None:
        raise NotImplementedError


class ConsoleVolumeBackend(VolumeBackend):
    name = "dry-run"

    def set_volume(self, percent: int) -> None:
        print(f"dry-run system volume: {clamp_percent(percent):3d}%")


class WindowsSystemVolumeBackend(VolumeBackend):
    """Control the Windows master system volume through pycaw.

    All pycaw/comtypes work runs in a dedicated STA thread to avoid the COM
    apartment conflict with Bleak, which requires MTA on the main asyncio thread.
    """

    name = "windows-system-volume"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise SystemVolumeUnavailable(
                "system volume control is currently implemented for Windows only"
            )

        self._queue: queue.SimpleQueue[int | None] = queue.SimpleQueue()
        self._ready = threading.Event()
        self._init_error: Exception | None = None

        threading.Thread(target=self._worker, daemon=True).start()
        self._ready.wait()

        if self._init_error is not None:
            raise SystemVolumeUnavailable(str(self._init_error)) from self._init_error

    def _worker(self) -> None:
        # This thread gets its own COM apartment (STA via comtypes' import-time
        # CoInitializeEx), isolated from the MTA apartment that WinRT/Bleak
        # uses on the main asyncio thread.
        try:
            pycaw = import_module("pycaw.pycaw")
            devices = pycaw.AudioUtilities.GetSpeakers()
            vol = getattr(devices, "EndpointVolume", None)
            if vol is None:
                comtypes = import_module("comtypes")
                interface = devices.Activate(
                    pycaw.IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
                )
                vol = interface.QueryInterface(pycaw.IAudioEndpointVolume)
        except Exception as exc:
            self._init_error = exc
            self._ready.set()
            return

        self._ready.set()

        while True:
            val = self._queue.get()
            if val is None:
                return
            try:
                vol.SetMasterVolumeLevelScalar(val / 100.0, None)
            except Exception:
                pass

    def set_volume(self, percent: int) -> None:
        self._queue.put(clamp_percent(percent))


def build_volume_backend(dry_run: bool = False) -> VolumeBackend:
    if dry_run:
        return ConsoleVolumeBackend()

    try:
        return WindowsSystemVolumeBackend()
    except SystemVolumeUnavailable as exc:
        print(f"system volume unavailable: {exc}")
        print("falling back to dry-run mode; no computer volume will be changed")
    return ConsoleVolumeBackend()


@dataclass
class RateLimitedVolume:
    backend: VolumeBackend
    min_change: int = 1
    min_interval_s: float = 0.0

    def __post_init__(self) -> None:
        self._last_percent: int | None = None
        self._last_update_s = 0.0

    def set_volume(self, percent: int) -> bool:
        target = clamp_percent(percent)
        now = time.monotonic()
        changed_enough = (
            self._last_percent is None
            or abs(target - self._last_percent) >= self.min_change
        )
        waited_enough = now - self._last_update_s >= self.min_interval_s

        if changed_enough and waited_enough:
            self.backend.set_volume(target)
            self._last_percent = target
            self._last_update_s = now
            return True
        return False
