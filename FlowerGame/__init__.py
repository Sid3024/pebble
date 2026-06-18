"""
FlowerGame -- cooperative and competitive flower-growing game for the Pebble project.

Players hold Pebble IMU sensor pods and shake them to grow virtual flowers.
In single-player (cooperative) mode every pod contributes to a shared garden.
In competitive mode, players split into two teams and race to grow more flowers
before the timer runs out.

Package layout:
    __main__.py        : Entry point when run as ``python -m FlowerGame``.
    main.py            : CLI parser and top-level async orchestrator (BLE + WS).
    simulator.py       : Generates synthetic window sums for hardware-free testing.
    config/config.py   : FlowerConfig dataclass with every tunable parameter.
    engine/controller.py   : FlowerController -- single-team game logic.
    engine/competitive.py  : CompetitiveFlowerController -- two-team game logic.
    ws/server.py       : WebSocket server and session orchestrator.
    ble/client.py      : Re-exports the shared PebbleClient for convenience.

Dependencies:
    - websockets : Async WebSocket server for the dashboard.
    - bleak      : BLE communication with sensor pods (via the shared ble/ package).
    - effort     : Baseline calculation helpers (external package).
"""
