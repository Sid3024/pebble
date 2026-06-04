"""
LEDClient — Python BLE client for the LED display MCU.

Connects to a "PebbleLED_XXXXXX" device and pushes 2-byte state packets
at UPDATE_HZ.  Packet format (must match led/led.h + led_config.h):

    byte[0]  ratio   0 = full Team 2, 128 = 50/50, 255 = full Team 1
    byte[1]  phase   see PHASE_* constants below
"""
from __future__ import annotations

import asyncio

from bleak import BleakClient

# ── Must match firmware/LEDLight/src/config/led_config.h ─────
LED_SERVICE_UUID = "b1c2d3e4-f5a6-7890-abcd-ef1234567890"
LED_CMD_UUID     = "b1c2d3e4-f5a6-7890-abcd-ef1234567891"

# ── Must match firmware/LEDLight/src/led/led.h ───────────────
PHASE_PLAYING   = 0
PHASE_TEAM0_WIN = 1
PHASE_TEAM1_WIN = 2
PHASE_TIE       = 3
PHASE_WAITING   = 4

UPDATE_HZ = 10   # state pushes per second


class LEDClient:
    """Connects to the LED MCU and streams encoded game state."""

    def __init__(self, device) -> None:
        self._device = device
        self.name    = device.name

    async def run(self, state_getter) -> None:
        """
        Continuously connect and push state.
        state_getter: callable () → dict  (the server's get_game_state())
        """
        RETRY_DELAY = 5.0
        interval    = 1.0 / UPDATE_HZ

        while True:
            try:
                async with BleakClient(self._device) as client:
                    print(f"[LED] connected to {self.name}")
                    while client.is_connected:
                        packet = self._encode(state_getter())
                        try:
                            await client.write_gatt_char(
                                LED_CMD_UUID, packet, response=False)
                        except Exception:
                            pass   # stale connection; outer loop will reconnect
                        await asyncio.sleep(interval)
                print(f"[LED] disconnected — retrying in {RETRY_DELAY:.0f}s")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[LED] error: {exc} — retrying in {RETRY_DELAY:.0f}s")
            await asyncio.sleep(RETRY_DELAY)

    # ── Encoding ──────────────────────────────────────────────

    def _encode(self, state: dict) -> bytes:
        if not state:
            return bytes([128, PHASE_WAITING])

        mode  = state.get("mode",  "single")
        phase = state.get("phase", "waiting")

        # LED display only makes sense in competitive mode
        if mode != "competitive":
            return bytes([128, PHASE_WAITING])

        if phase == "won":
            winner = state.get("winner")
            if winner == 0:
                return bytes([255, PHASE_TEAM0_WIN])
            elif winner == 1:
                return bytes([0,   PHASE_TEAM1_WIN])
            else:
                return bytes([128, PHASE_TIE])

        if phase != "playing":
            return bytes([128, PHASE_WAITING])

        # Compute ratio from live scores
        teams = state.get("teams", [])
        s0    = next((t.get("score", 0) for t in teams if t["id"] == 0), 0)
        s1    = next((t.get("score", 0) for t in teams if t["id"] == 1), 0)
        total = s0 + s1

        if total == 0:
            ratio = 128        # 0-0: split 50/50
        elif s0 == 0:
            ratio = 0          # only Team 2 has scored: full Team 2 colour
        elif s1 == 0:
            ratio = 255        # only Team 1 has scored: full Team 1 colour
        else:
            # Both teams scoring — keep a visible boundary in the middle
            ratio = max(1, min(254, int(s0 / total * 255)))

        return bytes([ratio, PHASE_PLAYING])
