from __future__ import annotations

import asyncio
import json

import websockets
import websockets.server

from ..config.config import FlowerConfig
from ..engine.controller import FlowerController
from ..engine.competitive import CompetitiveFlowerController


class FlowerWSServer:
    """
    WebSocket server and session orchestrator.

    - Owns the active controller (single or competitive).
    - Exposes process_window() so BLE clients treat the server as the controller.
    - Creates the right controller when the dashboard sends {"action":"start","mode":"..."}.
    - Resets to waiting state (no controller) on {"action":"reset"}.
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._controller: FlowerController | CompetitiveFlowerController | None = None
        self._clients: set[websockets.server.WebSocketServerProtocol] = set()

    # ── BLE / simulator interface ─────────────────────────────

    def process_window(self, device_name: str, window_sum: float) -> None:
        if self._controller is not None:
            self._controller.process_window(device_name, window_sum)

    def process_imu_window(self, device_name: str, imu_window) -> None:
        if self._controller is not None:
            fn = getattr(self._controller, "process_imu_window", None)
            if fn:
                fn(device_name, imu_window)
            else:
                self._controller.process_window(device_name, imu_window.effort_fallback)

    def get_game_state(self) -> dict:
        """Public accessor for the current game state (used by LEDClient)."""
        return self._get_state()

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        fn = getattr(self._controller, "pop_vibration_commands", None)
        return fn(device_name) if fn else []

    # ── Internal state helpers ────────────────────────────────

    def _get_state(self) -> dict:
        if self._controller is None:
            state = {
                "mode":           "single",
                "phase":          "waiting",
                "time_remaining": 0.0,
                "duration":       self._config.default_duration,
                "score":          0.0,
                "progress":       0.0,
                "num_devices":    0,
                "devices":        {},
                "plants":         [],
            }
        else:
            state = self._controller.get_state()
        state["show_match_percent"] = self._config.show_match_percent == "show"
        state["button_points"] = self._config.button_points
        return state

    def _handle_action(self, msg: dict) -> None:
        action   = msg.get("action")
        duration = int(msg.get("duration", self._config.default_duration))
        if action == "start":
            mode = msg.get("mode", "single")
            if mode == "competitive":
                self._controller = CompetitiveFlowerController(self._config)
            else:
                self._controller = FlowerController(self._config)
            self._controller.start_session(duration)
        elif action == "next_team":
            if hasattr(self._controller, "next_team"):
                self._controller.next_team()
        elif action == "confirm_instructor":
            if hasattr(self._controller, "confirm_instructor"):
                self._controller.confirm_instructor()
        elif action == "begin_game":
            if hasattr(self._controller, "begin_game"):
                self._controller.begin_game()
        elif action == "add_score":
            if self._config.button_points and hasattr(self._controller, "add_score"):
                self._controller.add_score(int(msg.get("team", 0)), int(msg.get("amount", 1)))
        elif action == "reset":
            self._controller = None

    # ── WebSocket handler ─────────────────────────────────────

    async def _handler(self, websocket: websockets.server.WebSocketServerProtocol) -> None:
        self._clients.add(websocket)
        print(f"[WS] dashboard connected ({len(self._clients)} total)")
        try:
            await websocket.send(json.dumps(self._get_state()))
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                self._handle_action(msg)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            print(f"[WS] dashboard disconnected ({len(self._clients)} remaining)")

    async def _broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.broadcast_interval_s)
            if not self._clients:
                continue
            payload = json.dumps(self._get_state())
            dead = set()
            for ws in list(self._clients):
                try:
                    await ws.send(payload)
                except websockets.exceptions.ConnectionClosed:
                    dead.add(ws)
            self._clients -= dead

    async def run(self) -> None:
        broadcast_task = asyncio.create_task(self._broadcast_loop())
        async with websockets.serve(
            self._handler,
            self._config.ws_host,
            self._config.ws_port,
        ):
            print(
                f"[WS] server listening on "
                f"ws://{self._config.ws_host}:{self._config.ws_port}"
            )
            await asyncio.Future()
        broadcast_task.cancel()
