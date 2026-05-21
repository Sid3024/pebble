# Volume Game

The volume game maps movement effort from the XIAO ESP32S3 accelerometer/IMU to music volume. Higher effort produces louder music.

## Folder Map

- `run_volume_game.py` - command-line entry point.
- `volume_game/effort.py` - raw IMU to effort calculation and effort-to-volume mapping.
- `volume_game/inputs.py` - serial input, simulator input, and line parsers.
- `volume_game/volume.py` - computer system-volume control. Uses `pycaw` on Windows, with a dry-run fallback.
- `tests/test_effort.py` - mapping and parser tests.

## Serial Data Formats

The Python app accepts any of these lines from firmware:

```text
0.73
effort=0.73
{"effort": 0.73}
0.02,-0.01,1.36
0.02,-0.01,1.36,4.2,0.0,-1.5
```

If the line contains `effort`, that value is used directly. If it contains raw accelerometer values `ax, ay, az`, the app calculates effort by removing the normal 1 g gravity magnitude and smoothing the result. Optional `gx, gy, gz` values add a small rotation contribution.

## Run

Install the serial and system-volume dependencies:

```powershell
python -m pip install -r volume\requirements.txt
```

Test without hardware. By default this attempts to change the computer's system volume:

```powershell
python volume\run_volume_game.py --simulate
```

Test without changing the computer's volume:

```powershell
python volume\run_volume_game.py --simulate --dry-run
```

Try one custom effort value and exit:

```powershell
python volume\run_volume_game.py --test-effort 0.8 --dry-run
```

Change the computer's system volume once and exit:

```powershell
python volume\run_volume_game.py --test-volume 25
```

List connected serial ports:

```powershell
python volume\run_volume_game.py --list-ports
```

Run with the XIAO:

```powershell
python volume\run_volume_game.py --port COM4 --baud 115200
```

Open a music file at startup:

```powershell
python volume\run_volume_game.py --port COM4 --music "C:\path\to\song.mp3"
```

If `pycaw` is missing, the app falls back to dry-run mode and prints the target volume instead of changing system audio.

## Tuning

Adjust these flags for your motion range:

```powershell
python volume\run_volume_game.py --port COM4 --min-effort 0.2 --max-effort 1.8 --min-volume 10 --max-volume 90
```

Start by moving the device slowly and quickly in simulator or serial mode, then set `--max-effort` close to the highest effort you can comfortably produce.

Default effort-to-volume mapping:

```text
0.2 -> 10%
0.4 -> 20%
0.6 -> 30%
0.8 -> 40%
1.0 -> 50%
1.2 -> 60%
1.4 -> 70%
1.6 -> 80%
1.8 -> 90%
2.0 -> 90% because the app caps at max-volume
```
