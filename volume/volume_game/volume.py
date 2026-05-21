from __future__ import annotations

from importlib import import_module
import sys
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
    """Control the Windows master system volume through pycaw."""

    name = "windows-system-volume"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise SystemVolumeUnavailable(
                "system volume control is currently implemented for Windows only"
            )

        pycaw = _load_module(
            "pycaw.pycaw",
            "Install pycaw with: python -m pip install pycaw",
        )

        devices = pycaw.AudioUtilities.GetSpeakers()
        self._volume = getattr(devices, "EndpointVolume", None)

        if self._volume is None:
            comtypes = _load_module(
                "comtypes",
                "Install pycaw and comtypes with: python -m pip install pycaw",
            )
            interface = devices.Activate(
                pycaw.IAudioEndpointVolume._iid_,
                comtypes.CLSCTX_ALL,
                None,
            )
            self._volume = interface.QueryInterface(pycaw.IAudioEndpointVolume)

    def set_volume(self, percent: int) -> None:
        self._volume.SetMasterVolumeLevelScalar(clamp_percent(percent) / 100.0, None)


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
    min_change: int = 2
    min_interval_s: float = 0.2

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


def _load_module(name: str, install_hint: str):
    try:
        return import_module(name)
    except ImportError as exc:
        raise SystemVolumeUnavailable(install_hint) from exc
