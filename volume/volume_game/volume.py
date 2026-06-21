"""
Volume / sound control module for the Volume game.

This file manages the computer's system audio volume. It provides an abstract
backend interface so the rest of the application does not care whether volume
is actually being changed (Windows) or just printed to the console (dry-run).

Architecture:
    VolumeBackend (abstract)
        |-- ConsoleVolumeBackend   (prints to stdout, no real volume change)
        |-- WindowsSystemVolumeBackend  (uses pycaw + comtypes to control
                                         Windows master volume via COM)
    RateLimitedVolume wraps any backend and suppresses redundant updates that
    are too small or too frequent, avoiding audio glitches from rapid changes.

Libraries used:
    - importlib.import_module: lazy import of pycaw/comtypes so they are only
      loaded when actually needed (and their absence produces a clear error).
    - sys: platform detection (Windows vs. other).
    - time: monotonic clock for rate-limiting.
    - dataclasses: for the RateLimitedVolume wrapper.

Classes:
    - SystemVolumeUnavailable: custom exception for volume init failures.
    - VolumeBackend: abstract base with a set_volume() contract.
    - ConsoleVolumeBackend: dry-run backend that only prints.
    - WindowsSystemVolumeBackend: real Windows system volume via pycaw.
    - RateLimitedVolume: rate-limiting decorator around any backend.

Functions:
    - clamp_percent(): restrict a value to [0, 100].
    - build_volume_backend(): factory that picks the best available backend.
    - _load_module(): helper for lazy imports with user-friendly error messages.

Fits into the Pebble project as the output layer of the Volume game -- it
receives volume percentages from the effort -> volume mapping (effort.py) and
applies them to the actual audio hardware.
"""

from __future__ import annotations

from importlib import import_module
import sys
import time
from dataclasses import dataclass


class SystemVolumeUnavailable(RuntimeError):
    """Raised when the computer's system-volume backend cannot be started.

    This typically happens when pycaw or comtypes are not installed, or when
    the script is running on a non-Windows platform.
    """


def clamp_percent(percent: int) -> int:
    """Clamp a volume percentage to the valid range [0, 100].

    Also coerces the input to int, so floats are truncated before clamping.
    """
    return max(0, min(100, int(percent)))


class VolumeBackend:
    """Abstract base class for volume control backends.

    Subclasses must override set_volume(). The ``name`` attribute is used
    in log messages so the user knows which backend is active.
    """

    name = "base"

    def set_volume(self, percent: int) -> None:
        """Set the system volume to the given percentage [0..100]."""
        raise NotImplementedError


class ConsoleVolumeBackend(VolumeBackend):
    """Dry-run backend that prints the target volume instead of changing it.

    Used when --dry-run is passed or when the real backend is unavailable.
    """

    name = "dry-run"

    def set_volume(self, percent: int) -> None:
        """Print the volume target to stdout without changing real audio."""
        print(f"dry-run system volume: {clamp_percent(percent):3d}%")


class WindowsSystemVolumeBackend(VolumeBackend):
    """Control the Windows master system volume through pycaw.

    On construction, lazily imports pycaw and comtypes, obtains the default
    audio endpoint (speakers), and acquires the IAudioEndpointVolume COM
    interface. All subsequent set_volume() calls go through that interface.

    Raises SystemVolumeUnavailable if not on Windows or if pycaw/comtypes
    cannot be imported.
    """

    name = "windows-system-volume"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise SystemVolumeUnavailable(
                "system volume control is currently implemented for Windows only"
            )

        # Lazily import pycaw so the rest of the game works without it installed.
        pycaw = _load_module(
            "pycaw.pycaw",
            "Install pycaw with: python -m pip install pycaw",
        )

        devices = pycaw.AudioUtilities.GetSpeakers()
        self._volume = getattr(devices, "EndpointVolume", None)

        # Some pycaw versions do not expose EndpointVolume directly;
        # fall back to manual COM activation via comtypes.
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
        """Set the Windows master volume using a scalar in [0.0, 1.0]."""
        self._volume.SetMasterVolumeLevelScalar(clamp_percent(percent) / 100.0, None)


def build_volume_backend(dry_run: bool = False) -> VolumeBackend:
    """Factory function that returns the best available volume backend.

    If *dry_run* is True, always returns a ConsoleVolumeBackend. Otherwise,
    tries to create a WindowsSystemVolumeBackend and falls back to console
    output with a warning if that fails.
    """
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
    """Wrapper that suppresses redundant or too-frequent volume updates.

    Without rate-limiting, the event loop could call set_volume() on every
    sensor reading (10+ times per second), which may cause audio artefacts or
    excessive CPU usage from COM calls. This wrapper only forwards a
    set_volume() call to the underlying backend when:
        1. The new target differs from the last applied value by at least
           *min_change* percentage points, AND
        2. At least *min_interval_s* seconds have elapsed since the last update.

    Attributes:
        backend:        the actual VolumeBackend to delegate to.
        min_change:     minimum absolute change (in percentage points) required
                        to trigger a real update (default 2).
        min_interval_s: minimum seconds between consecutive real updates
                        (default 0.2).
    """

    backend: VolumeBackend
    min_change: int = 2
    min_interval_s: float = 0.2

    def __post_init__(self) -> None:
        """Initialise internal tracking state after dataclass construction."""
        self._last_percent: int | None = None
        self._last_update_s = 0.0

    def set_volume(self, percent: int) -> bool:
        """Set volume if the change is large enough and enough time has passed.

        Returns True if the volume was actually forwarded to the backend,
        False if the update was suppressed.
        """
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
    """Import a module by name, raising SystemVolumeUnavailable on failure.

    Provides a user-friendly install hint instead of a raw ImportError, which
    is especially helpful for pycaw/comtypes since they are not in the
    standard library.
    """
    try:
        return import_module(name)
    except ImportError as exc:
        raise SystemVolumeUnavailable(install_hint) from exc
