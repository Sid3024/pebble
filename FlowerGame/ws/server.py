from __future__ import annotations

import asyncio
import json

import websockets
import websockets.server

from ..config.config import FlowerConfig
from ..engine.controller import FlowerController


class FlowerWSServer:
    """
    WebSocket server that bridges FlowerController state to the browser dashboard.

    - Broadcasts game state to all connected clients every broadcast_interval_s.
    - Receives {"action": "start"} and {"action": "reset"} from the dashboard.
    """

    def __init__(self, controller: FlowerController, config: FlowerConfig) -> None:
        self._controller = controller
        self._config = config
        self._clients: set[websockets.server.WebSocketServerProtocol] = set()

    async def _handler(self, websocket: websockets.server.WebSocketServerProtocol) -> None:
        self._clients.add(websocket)
        print(f"[WS] dashboard connected ({len(self._clients)} total)")
        try:
            # Send current state immediately on connect
            await websocket.send(json.dumps(self._controller.get_state()))
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                action = msg.get("action")
                if action == "start":
                    self._controller.start_session()
                elif action == "reset":
                    self._controller.reset()
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
            payload = json.dumps(self._controller.get_state())
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
            await asyncio.Future()  # run until cancelled
        broadcast_task.cancel()
