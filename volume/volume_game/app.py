"""
Main application module for the Volume game.

This file wires together all the other modules into a complete command-line
application. It parses CLI arguments, sets up the effort source (serial or
simulated), builds the volume backend, and runs the main event loop that
continuously reads effort events and adjusts the system volume accordingly.

Execution flow:
    1. Parse command-line arguments (port, baud rate, simulation mode, etc.).
    2. Handle quick-exit modes: --list-ports, --test-volume, --test-effort.
    3. Build an EffortCalculator and choose an EffortSource (serial or simulated).
    4. Enter the main loop: for each EffortEvent, map effort to volume and
       apply it through the rate-limited volume backend.
    5. Exit cleanly on Ctrl+C.

Libraries used:
    - argparse: CLI argument parsing.
    - os: os.startfile() for opening music on Windows.
    - platform: detecting the OS for platform-specific music opening.
    - pathlib.Path: file path handling for the --music option.

Functions:
    - main(): the primary entry point; returns an int exit code.
    - _open_music(): helper to open a music file in the system default player.

Fits into the Pebble project as the orchestration layer of the Volume game,
called by run_volume_game.py. It ties the input layer (inputs.py), the effort
calculation layer (effort.py), and the volume output layer (volume.py) into
one cohesive application.
"""

from __future__ import annotations

import argparse
import os
import platform
from pathlib import Path

from .effort import EffortCalculator, map_effort_to_volume
from .inputs import SerialEffortSource, SimulatedEffortSource, list_serial_ports
from .volume import RateLimitedVolume, build_volume_backend


def main() -> int:
    """Entry point for the Volume game CLI.

    Parses command-line arguments, selects the appropriate effort source and
    volume backend, then runs the main loop. Returns an integer exit code
    (0 for success).

    Supported modes:
        --list-ports:   Print available serial ports and exit.
        --test-volume:  Set the system volume once and exit (for debugging).
        --test-effort:  Convert a single effort value to volume and exit.
        --simulate:     Use a sine-wave simulator instead of real hardware.
        --port COMx:    Read from a real XIAO ESP32S3 pod on the given port.
        (no --port):    Falls back to simulation mode automatically.
    """
    parser = argparse.ArgumentParser(
        description="Map XIAO ESP32S3 accelerometer/IMU effort to music volume."
    )
    parser.add_argument("--port", help="Serial port from the XIAO, for example COM4.")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--simulate", action="store_true", help="Run without hardware.")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--music", help="Optional music file to open in the default player.")
    parser.add_argument(
        "--test-effort",
        type=float,
        help="Set volume once using a custom effort value, then exit.",
    )
    parser.add_argument(
        "--test-volume",
        type=int,
        help="Set system volume once to this percentage, then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print target volume without changing the computer's system volume.",
    )
    parser.add_argument("--min-effort", type=float, default=0.2)
    parser.add_argument("--max-effort", type=float, default=1.8)
    parser.add_argument("--min-volume", type=int, default=10)
    parser.add_argument("--max-volume", type=int, default=90)
    args = parser.parse_args()

    # Quick-exit: list available serial ports and stop.
    if args.list_ports:
        ports = list_serial_ports()
        print("\n".join(ports) if ports else "No serial ports found.")
        return 0

    # Optionally launch a music file in the system default player.
    if args.music:
        _open_music(Path(args.music))

    # Build the volume backend (real Windows volume or dry-run console).
    # Rate-limiting is disabled (min_change=0, min_interval_s=0.0) so every
    # event triggers an update -- useful for the test modes below.
    volume = RateLimitedVolume(
        build_volume_backend(dry_run=args.dry_run),
        min_change=0,
        min_interval_s=0.0,
    )

    # Quick-exit: set volume to an explicit percentage and stop.
    if args.test_volume is not None:
        volume.set_volume(args.test_volume)
        print(f"test volume={args.test_volume}% backend={volume.backend.name}")
        return 0

    # Quick-exit: convert a single effort value to a volume and stop.
    if args.test_effort is not None:
        target = map_effort_to_volume(
            args.test_effort,
            args.min_effort,
            args.max_effort,
            args.min_volume,
            args.max_volume,
        )
        volume.set_volume(target)
        print(
            f"test effort={args.test_effort:.2f} mapped volume={target}% "
            f"backend={volume.backend.name}"
        )
        return 0

    # --- Main event loop ---
    # Create an effort calculator and choose the appropriate data source.
    calculator = EffortCalculator()
    source = (
        SimulatedEffortSource()
        if args.simulate or not args.port
        else SerialEffortSource(args.port, args.baud, calculator)
    )

    mode = "simulator" if args.simulate or not args.port else f"serial {args.port}"
    print(
        f"Volume game running in {mode} mode using {volume.backend.name}. "
        "Press Ctrl+C to stop."
    )

    try:
        for event in source.events():
            # Map the effort from this event to a volume percentage.
            target = map_effort_to_volume(
                event.effort,
                args.min_effort,
                args.max_effort,
                args.min_volume,
                args.max_volume,
            )
            # Apply the volume; the rate limiter decides whether to actually
            # forward the call to the backend.
            changed = volume.set_volume(target)
            # Display a '*' marker when the volume actually changed.
            marker = "*" if changed else " "
            print(
                f"{marker} effort={event.effort:5.2f} source={event.source:<13} volume={target:3d}%"
            )
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def _open_music(path: Path) -> None:
    """Open a music file in the OS default media player.

    On Windows, uses os.startfile() which launches the default application
    for the file type. On other platforms, just prints the path for the user
    to open manually.

    Does nothing (with a warning) if the file does not exist.
    """
    if not path.exists():
        print(f"music file not found: {path}")
        return

    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        print(f"Open this music file in your player: {path}")
