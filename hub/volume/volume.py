"""
Hub volume control module -- thread-safe system audio volume backend.

This file is the Hub variant of the volume control layer, designed to work
alongside BLE (Bleak) communication with XIAO ESP32S3 pods. The key
difference from the simpler ``volume/volume_game/volume.py`` is that the
Windows backend here runs all COM/pycaw operations in a **dedicated STA
(Single-Threaded Apartment) worker thread**. This is necessary because:

    - Bleak (the BLE library) requires the main asyncio thread to use the MTA
      (Multi-Threaded Apartment) COM model for WinRT interop.
    - pycaw/comtypes must run in STA to access the audio endpoint correctly.
    - Running both in the same thread causes COM apartment conflicts.

The solution is a producer-consumer pattern: set_volume() enqueues the target
percentage onto a SimpleQueue, and the worker thread (running in its own STA)
dequeues and applies it through the IAudioEndpointVolume COM interface.

Libraries used:
    - importlib.import_module: lazy import of pycaw/comtypes.
    - queue.SimpleQueue: thread-safe, lock-free queue for volume commands.
    - sys: platform detection.
    - threading: dedicated worker thread for COM operations; Event for init sync.
    - time: monotonic clock for rate-limiting.
    - dataclasses: for the RateLimitedVolume wrapper.

Classes:
    - SystemVolumeUnavailable: exception for volume init failures.
    - VolumeBackend: abstract base class.
    - ConsoleVolumeBackend: dry-run backend (prints only).
    - WindowsSystemVolumeBackend: real volume control via a background STA thread.
    - RateLimitedVolume: rate-limiting wrapper to avoid redundant updates.

Functions:
    - clamp_percent(): restrict a value to [0, 100].
    - build_volume_backend(): factory that picks the best available backend.

Fits into the Pebble project as the Hub's shared volume control infrastructure,
used when BLE pod data drives system volume alongside other async tasks.
"""

from __future__ import annotations

from importlib import import_module
import queue
import sys
import threading
import time
from dataclasses import dataclass


class SystemVolumeUnavailable(RuntimeError):
    """Raised when the computer's system-volume backend cannot be started.

    Typical causes: non-Windows platform, missing pycaw/comtypes packages,
    or no audio output device available.
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

    Used when --dry-run is passed, or as a fallback when the real Windows
    backend cannot be initialised.
    """

    name = "dry-run"

    def set_volume(self, percent: int) -> None:
        """Print the volume target to stdout without changing real audio."""
        print(f"dry-run system volume: {clamp_percent(percent):3d}%")


class WindowsSystemVolumeBackend(VolumeBackend):
    """Control the Windows master system volume through pycaw.

    All pycaw/comtypes work runs in a dedicated STA thread to avoid the COM
    apartment conflict with Bleak, which requires MTA on the main asyncio thread.

    Design:
        - __init__() starts a daemon worker thread and blocks until it reports
          ready (or an error).
        - The worker thread imports pycaw/comtypes in its own COM apartment,
          obtains the IAudioEndpointVolume interface, and enters a get() loop.
        - set_volume() is non-blocking: it enqueues the target percentage onto
          a SimpleQueue. The worker dequeues and applies it.
        - Sending None through the queue signals the worker to exit (though in
          practice the daemon flag handles cleanup on process exit).
    """

    name = "windows-system-volume"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise SystemVolumeUnavailable(
                "system volume control is currently implemented for Windows only"
            )

        # Queue for sending volume targets (int) or shutdown signal (None)
        # from the main thread to the STA worker.
        self._queue: queue.SimpleQueue[int | None] = queue.SimpleQueue()
        self._ready = threading.Event()
        self._init_error: Exception | None = None

        # Start the STA worker thread; it will signal _ready when initialised.
        threading.Thread(target=self._worker, daemon=True).start()
        self._ready.wait()

        if self._init_error is not None:
            raise SystemVolumeUnavailable(str(self._init_error)) from self._init_error

    def _worker(self) -> None:
        """Background thread that owns the COM STA and processes volume commands.

        This thread gets its own COM apartment (STA via comtypes' import-time
        CoInitializeEx), isolated from the MTA apartment that WinRT/Bleak
        uses on the main asyncio thread. It initialises the audio endpoint once,
        then loops forever processing volume commands from the queue.
        """
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

        # Signal that initialisation succeeded.
        self._ready.set()

        # Process volume commands until a None sentinel is received.
        while True:
            val = self._queue.get()
            if val is None:
                return
            try:
                vol.SetMasterVolumeLevelScalar(val / 100.0, None)
            except Exception:
                # Swallow errors from the COM call (e.g. device removed) to
                # keep the worker alive for future requests.
                pass

    def set_volume(self, percent: int) -> None:
        """Enqueue a volume change to be applied by the STA worker thread.

        Non-blocking: the actual COM call happens asynchronously in the worker.
        """
        self._queue.put(clamp_percent(percent))


def build_volume_backend(dry_run: bool = False) -> VolumeBackend:
    """Factory function that returns the best available volume backend.

    If *dry_run* is True, always returns a ConsoleVolumeBackend. Otherwise,
    tries to create a WindowsSystemVolumeBackend (with its background STA
    thread) and falls back to console output with a warning if that fails.
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

    Prevents flooding the backend (especially the COM-based Windows backend)
    with near-identical volume commands. A set_volume() call is only forwarded
    to the backend when both conditions are met:
        1. The new target differs from the last applied value by at least
           *min_change* percentage points.
        2. At least *min_interval_s* seconds have elapsed since the last update.

    Attributes:
        backend:        the actual VolumeBackend to delegate to.
        min_change:     minimum absolute change (in percentage points) required
                        to trigger a real update (default 1).
        min_interval_s: minimum seconds between consecutive real updates
                        (default 0.0 -- no time gating).
    """

    backend: VolumeBackend
    min_change: int = 1
    min_interval_s: float = 0.0

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
