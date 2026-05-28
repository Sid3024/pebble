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

    # ── Internal state helpers ────────────────────────────────

    def _get_state(self) -> dict:
        if self._controller is None:
            return {
                "mode":         "single",
                "phase":        "waiting",
                "progress":     0.0,
                "total_growth": 0.0,
                "total_needed": self._config.total_growth_needed,
                "num_devices":  0,
                "devices":      {},
                "plants":       [{"id": i, "growth": 0.0}
                                 for i in range(self._config.num_plants)],
            }
        return self._controller.get_state()

    def _handle_action(self, msg: dict) -> None:
        action = msg.get("action")
        if action == "start":
            mode = msg.get("mode", "single")
            if mode == "competitive":
                self._controller = CompetitiveFlowerController(self._config)
            else:
                self._controller = FlowerController(self._config)
            self._controller.start_session()
        elif action == "reset":
            self._controller = None   # return to waiting; user picks mode again

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
