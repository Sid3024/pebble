"""
FlowerGame.engine -- game logic for flower growth, scoring, and team management.

This package contains the core controllers that process IMU data from pods
and turn it into flower growth:

    - controller.py    : FlowerController for single-team (cooperative) mode.
                         Also defines PersonGrowthTracker (per-device baseline
                         and scoring) and DeviceState.
    - competitive.py   : CompetitiveFlowerController for two-team competitive
                         mode, with team selection, balanced assignment, and
                         per-team scoring.

Both controllers expose the same interface:
    process_window(device_name, window_sum)  -- feed in IMU data
    start_session(duration_seconds)          -- begin a timed game
    reset()                                  -- return to waiting state
    get_state()                              -- snapshot for the dashboard
    pop_vibration_commands(device_name)       -- drain pending haptic commands
"""
