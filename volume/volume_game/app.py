from __future__ import annotations

import argparse
import os
import platform
from pathlib import Path

from .effort import EffortCalculator, map_effort_to_volume
from .inputs import SerialEffortSource, SimulatedEffortSource, list_serial_ports
from .volume import RateLimitedVolume, build_volume_backend


def main() -> int:
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

    if args.list_ports:
        ports = list_serial_ports()
        print("\n".join(ports) if ports else "No serial ports found.")
        return 0

    if args.music:
        _open_music(Path(args.music))

    volume = RateLimitedVolume(
        build_volume_backend(dry_run=args.dry_run),
        min_change=0,
        min_interval_s=0.0,
    )

    if args.test_volume is not None:
        volume.set_volume(args.test_volume)
        print(f"test volume={args.test_volume}% backend={volume.backend.name}")
        return 0

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
            target = map_effort_to_volume(
                event.effort,
                args.min_effort,
                args.max_effort,
                args.min_volume,
                args.max_volume,
            )
            changed = volume.set_volume(target)
            marker = "*" if changed else " "
            print(
                f"{marker} effort={event.effort:5.2f} source={event.source:<13} volume={target:3d}%"
            )
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def _open_music(path: Path) -> None:
    if not path.exists():
        print(f"music file not found: {path}")
        return

    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        print(f"Open this music file in your player: {path}")
