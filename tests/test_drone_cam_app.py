from drone_cam_app import create_app


class StubDroneCameraService:
    def __init__(self):
        self.settings = {
            "camera_name": "Test Drone Cam",
            "wifi_ssid": "HFUN_TEST",
            "wifi_host": "192.168.1.1",
            "stream_url": "rtsp://192.168.1.1:554/live/ch0",
            "viewer_mode": "proxy",
            "notes": "test settings",
        }
        self.disconnected = False

    def get_settings(self):
        return self.settings

    def update_settings(self, payload):
        self.settings = {**self.settings, **payload}
        return self.settings

    def get_status(self):
        return {
            "settings": self.settings,
            "stream_scheme": "rtsp",
            "opencv_available": True,
            "proxy_ready": True,
            "active_stream_url": self.settings["stream_url"],
            "last_error": None,
            "viewer_hint": "Proxy mode is active.",
        }

    def probe(self, payload=None):
        payload = payload or {}
        stream_url = payload.get("stream_url", self.settings["stream_url"])
        return {
            "ok": True,
            "scheme": stream_url.split(":", 1)[0],
            "host": "192.168.1.1",
            "port": 554,
            "detail": "Reached test target.",
            "browser_support": "Use proxy mode.",
        }

    def stop_stream(self):
        self.disconnected = True

    def open_stream(self):
        return iter(
            [
                (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-store\r\n\r\n"
                    b"fakejpeg"
                    b"\r\n"
                )
            ]
        )


def build_client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DRONE_CAMERA_SETTINGS_PATH": tmp_path / "drone_camera_settings.json",
            "DRONE_CAMERA_SERVICE": StubDroneCameraService(),
        }
    )
    return app.test_client()


def test_standalone_drone_cam_routes(tmp_path):
    client = build_client(tmp_path)

    assert client.get("/").status_code == 200

    settings_response = client.get("/api/settings")
    assert settings_response.status_code == 200
    assert settings_response.get_json()["camera_name"] == "Test Drone Cam"

    update_response = client.post(
        "/api/settings",
        json={
            "camera_name": "Bench Camera",
            "stream_url": "rtsp://192.168.1.1:8554/live/ch0",
            "viewer_mode": "proxy",
            "wifi_host": "192.168.1.1",
            "wifi_ssid": "HFUN_TEST",
            "notes": "updated",
        },
    )
    assert update_response.status_code == 200
    assert update_response.get_json()["settings"]["camera_name"] == "Bench Camera"

    status_response = client.get("/api/status")
    assert status_response.status_code == 200
    assert status_response.get_json()["proxy_ready"] is True

    probe_response = client.post("/api/probe", json={"stream_url": "rtsp://192.168.1.1:8554/live/ch0"})
    assert probe_response.status_code == 200
    assert probe_response.get_json()["ok"] is True

    stream_response = client.get("/api/stream")
    assert stream_response.status_code == 200
    assert stream_response.mimetype == "multipart/x-mixed-replace"
    assert b"fakejpeg" in stream_response.data

    disconnect_response = client.post("/api/disconnect")
    assert disconnect_response.status_code == 200
    assert disconnect_response.get_json()["status"] == "success"
