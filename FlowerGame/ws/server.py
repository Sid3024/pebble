"""
WebSocket server and session orchestrator for the FlowerGame.

This module contains FlowerWSServer, which is the central hub connecting
BLE data input to game logic and dashboard output.

Architecture overview:

    BLE pods / simulator
          |
          | process_window(device_name, window_sum)
          v
    FlowerWSServer  (this class)
          |
          |--- owns ---> FlowerController or CompetitiveFlowerController
          |                     (created/destroyed by dashboard actions)
          |
          |--- broadcasts game state ---> Dashboard(s) via WebSocket
          |
          |<-- receives actions --------- Dashboard(s) via WebSocket
          |       {"action":"start","mode":"single","duration":120}
          |       {"action":"next_team"}
          |       {"action":"begin_game"}
          |       {"action":"reset"}

Key responsibilities:
    1. **Controller lifecycle** -- Creates the right controller (single or
       competitive) when the dashboard sends a "start" action, and destroys
       it on "reset".
    2. **Data proxy** -- Exposes process_window() and pop_vibration_commands()
       so BLE clients (and the simulator) can treat the WS server as if it
       were the game controller directly.
    3. **State broadcast** -- Runs a background loop that sends the full
       game state as JSON to every connected dashboard ~3 times per second
       (configurable via broadcast_interval_s).
    4. **Dashboard messaging** -- Each connected dashboard gets the current
       state immediately on connect, and can send JSON action messages to
       drive game phase transitions.

Dependencies:
    - websockets : Async WebSocket server library.
    - json       : Serialization of game state dicts.
    - asyncio    : Concurrent broadcast loop + WS server.

How it fits into Pebble:
    FlowerGame.main creates one FlowerWSServer, then runs it alongside the
    BLE client tasks (or simulator).  The dashboard (GameDashboard/index.html)
    connects via ws://localhost:8765 and both reads state and sends actions.
"""

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
    - Creates the right controller when the dashboard sends
      {"action":"start","mode":"..."}.
    - Resets to waiting state (no controller) on {"action":"reset"}.

    Attributes:
        _config:     FlowerConfig instance (read-only at runtime).
        _controller: The active game controller, or None when in "waiting" state.
        _clients:    Set of currently connected WebSocket client connections.
    """

    def __init__(self, config: FlowerConfig) -> None:
        """
        Args:
            config: FlowerConfig with WS host/port and other settings.
        """
        self._config = config
        self._controller: FlowerController | CompetitiveFlowerController | None = None
        self._clients: set[websockets.server.WebSocketServerProtocol] = set()

    # ── BLE / simulator interface ─────────────────────────────
    # These methods make the WS server look like a game controller to BLE clients.

    def process_window(self, device_name: str, window_sum: float) -> None:
        """
        Proxy: forward a window sum from a BLE pod to the active controller.

        If no controller exists (waiting state), the window is silently dropped.

        Args:
            device_name: BLE advertising name of the pod.
            window_sum:  Aggregated acceleration sum for one time window.
        """
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
        """
        Public accessor for the current game state.

        Used by external consumers (e.g. LEDClient) that need the game state
        but are not connected via WebSocket.
        """
        return self._get_state()

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        """
        Proxy: drain pending vibration commands from the active controller.

        Uses getattr() for safety -- if the controller does not implement
        pop_vibration_commands (or is None), returns an empty list.

        Args:
            device_name: BLE name of the pod.

        Returns:
            List of vibration pattern IDs, or [].
        """
        fn = getattr(self._controller, "pop_vibration_commands", None)
        return fn(device_name) if fn else []

    # ── Internal state helpers ────────────────────────────────

    def _get_state(self) -> dict:
        """
        Get the current game state as a dict.

        If no controller is active (waiting phase), returns a default "waiting"
        state with zeros so the dashboard always receives a valid structure.
        Otherwise delegates to the controller's get_state().
        """
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
        """
        Process a JSON action message received from the dashboard.

        Supported actions:
            "start"      : Create a new controller (single or competitive) and
                           start a session with the given duration.
            "next_team"  : Advance team selection (competitive mode only).
            "begin_game" : Start the countdown timer (competitive mode only).
            "reset"      : Destroy the controller, returning to waiting state.

        Args:
            msg: Parsed JSON dict with at least an "action" key.
        """
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
            # Only CompetitiveFlowerController has next_team()
            if hasattr(self._controller, "next_team"):
                self._controller.next_team()
        elif action == "confirm_instructor":
            if hasattr(self._controller, "confirm_instructor"):
                self._controller.confirm_instructor()
        elif action == "begin_game":
            # Only CompetitiveFlowerController has begin_game()
            if hasattr(self._controller, "begin_game"):
                self._controller.begin_game()
        elif action == "add_score":
            if self._config.button_points and hasattr(self._controller, "add_score"):
                self._controller.add_score(int(msg.get("team", 0)), int(msg.get("amount", 1)))
        elif action == "reset":
            # Destroy the controller -- game returns to waiting state
            self._controller = None

    # ── WebSocket handler ─────────────────────────────────────

    async def _handler(self, websocket: websockets.server.WebSocketServerProtocol) -> None:
        """
        Handle a single WebSocket connection from a dashboard client.

        Lifecycle:
            1. Register the connection in _clients.
            2. Send the current game state immediately (so the dashboard renders
               the correct initial view).
            3. Listen for incoming JSON messages and dispatch to _handle_action().
            4. On disconnect (or error), remove from _clients.

        Args:
            websocket: The WebSocket connection object from the websockets library.
        """
        self._clients.add(websocket)
        print(f"[WS] dashboard connected ({len(self._clients)} total)")
        try:
            # Send current state immediately on connect
            await websocket.send(json.dumps(self._get_state()))
            # Listen for action messages from the dashboard
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
        """
        Background task: broadcast game state to all connected dashboards.

        Runs forever.  Every broadcast_interval_s seconds, serializes the current
        game state to JSON and sends it to every connected WebSocket client.
        Dead connections (ConnectionClosed) are detected and removed.

        This is the primary way the dashboard stays updated -- it does NOT poll;
        the server pushes.
        """
        while True:
            await asyncio.sleep(self._config.broadcast_interval_s)
            if not self._clients:
                continue
            # Serialize once, send to all clients
            payload = json.dumps(self._get_state())
            dead = set()
            for ws in list(self._clients):
                try:
                    await ws.send(payload)
                except websockets.exceptions.ConnectionClosed:
                    dead.add(ws)
            # Clean up dead connections
            self._clients -= dead

    async def run(self) -> None:
        """
        Start the WebSocket server and the broadcast loop.

        Creates the broadcast loop as a background task, then starts the
        websockets server.  Both run until the process is cancelled.
        ``await asyncio.Future()`` blocks forever (the server handles
        connections via _handler callbacks).
        """
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
            await asyncio.Future()  # run forever
        broadcast_task.cancel()
