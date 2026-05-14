# Altitude Control Simulator

Standalone spacecraft and UAV altitude-control web app built in Python.

This project lives entirely inside `/Users/ethanjmathew/macro-tracker/attitude_control_simulator` and stays separate from the macro-tracker app logic.

## What It Is Now

The simulator is no longer just a CLI script. It now includes:

- A Flask web dashboard with live controls and local API endpoints.
- Quaternion-based attitude dynamics instead of Euler-only propagation.
- PID and LQR controller comparison with auto-tuning support.
- Spacecraft reaction-wheel and UAV quad-motor actuator models.
- Sensor noise plus plant uncertainty for more realistic runs.
- Scenario presets like tumble recovery, moving-target tracking, and disturbance rejection.
- Side-by-side scorecards and live 3D attitude animation.
- Exportable report bundles with CSV, PNG, JSON, and text summaries.

## Run The Web App

```bash
cd /Users/ethanjmathew/macro-tracker/attitude_control_simulator
python3 -m pip install -r requirements.txt
python3 webapp.py
```

Then open [http://127.0.0.1:5011](http://127.0.0.1:5011).
The simulator uses port `5011` by default so it does not collide with the macro tracker on port `5001`.

## Run The CLI

```bash
python3 simulator.py --vehicle spacecraft --controller both --report
```

Example tracking run:

```bash
python3 simulator.py \
  --vehicle uav \
  --scenario track_moving_target \
  --controller lqr \
  --sensor-noise-deg 0.15 \
  --sensor-rate-noise-deg-s 0.35
```

## Key Capabilities

- `spacecraft` and `uav` presets.
- `pid`, `lqr`, or side-by-side comparison mode.
- Quaternion propagation for 3-axis rigid-body attitude motion.
- Actuator lag and actuator-specific torque behavior.
- Sensor noise, sensor bias, inertia uncertainty, and damping uncertainty.
- Auto-tuned controller settings based on scenario severity.
- Preset scenarios:
  - `recover_from_tumble`
  - `track_moving_target`
  - `disturbance_rejection`
- Scorecards for settling, RMS error, final error, and control effort.
- Report export to `reports/`.

## Project Layout

- `simulator.py`: simulation engine, controller logic, CLI, export helpers.
- `webapp.py`: Flask dashboard and API endpoints.
- `templates/index.html`: dashboard page shell.
- `static/app.js`: UI logic, charts, animations, report actions.
- `static/styles.css`: dashboard styling.
- `tests/`: simulator and web endpoint tests.

## Run Tests

```bash
python3 -m pytest -q
```
