# Drone Camera Connect

Fresh standalone project for connecting a stripped drone camera to this Mac through a local Flask app.

## Goal

1. Connect this computer to the camera's Wi-Fi.
2. Let the app probe likely stream targets.
3. Use proxy mode so this Mac can view RTSP or UDP-style feeds in a normal browser.

## Run it

```bash
cd /path/to/drone_camera_connect
python3 -m pip install -r requirements.txt
python3 app.py
```

You can still launch it from the parent workspace if you prefer:

```bash
cd /path/to/parent/of/drone_camera_connect
python3 -m pip install -r drone_camera_connect/requirements.txt
python3 -m drone_camera_connect.app
```

Default URL:

- `http://127.0.0.1:5601`

## Project layout

- `drone_camera_connect/app.py`: Flask app and routes
- `drone_camera_connect/camera_service.py`: settings store, probing, and stream proxy logic
- `drone_camera_connect/templates/`: standalone flight-deck UI
- `drone_camera_connect/static/`: orange-glow styling
- `drone_camera_connect/tests/`: starter tests

## First target to try

- `rtsp://192.168.1.1:554/live/ch0`

If that does not work, the next best step is to inspect the original vendor app traffic while it talks to the camera so we can discover the real stream path and any control messages.
