# Drone Cam

Standalone Flask app for repurposed Wi-Fi drone cameras.

## Start it

```bash
python3 -m pip install -r requirements.txt
python3 drone_cam_app.py
```

By default it runs on `http://127.0.0.1:5501`.

## What it does

- saves the camera IP, stream URL, and viewer mode in `drone_camera_settings.json`
- probes likely RTSP / HTTP targets
- proxies RTSP-style feeds into an MJPEG stream your phone browser can display

## Typical workflow

1. Connect the computer running this app to the drone camera's Wi-Fi network.
2. Open `http://127.0.0.1:5501`.
3. Start with a likely stream URL such as `rtsp://192.168.1.1:554/live/ch0`.
4. Use `Probe target` to confirm the host and port are reachable.
5. Leave `Viewer mode` on `Proxy through this app` for RTSP or UDP feeds.
6. Open the same page on your phone using the server's LAN IP.

Notes:

- Proxy mode is the best option for RTSP because most phone browsers do not play RTSP directly.
- Direct modes are only for cameras that already expose MJPEG or browser-native video over HTTP.
- If the camera still does not render, capture packets from the original vendor app to discover the real stream path and any control commands.
