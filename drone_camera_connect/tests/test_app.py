from drone_camera_connect.app import create_app


class StubCameraService:
    def __init__(self):
        self.settings = {
            "camera_name": "Bench Camera",
            "wifi_ssid": "HFUN_TEST",
            "wifi_host": "192.168.1.1",
            "stream_url": "udp://@0.0.0.0:8080",
            "viewer_mode": "proxy",
            "notes": "test profile",
        }

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
            "recommended_viewer_mode": "proxy",
            "connection_summary": "UDP packets were detected on port 8080.",
            "stream_candidates": [
                {
                    "label": "UDP 8080",
                    "url": "udp://@0.0.0.0:8080",
                    "viewer_mode": "proxy",
                    "viewer_mode_label": "Proxy through this app",
                }
            ],
            "host_matches_stream": True,
            "udp_scan_result": {
                "ok": True,
                "capture_mode": "scan",
                "duration_seconds": 2.5,
                "active_port": 8080,
                "suggested_stream_url": "udp://@0.0.0.0:8080",
                "detail": "Detected UDP packets on port 8080.",
                "ports": [
                    {
                        "port": 8080,
                        "status": "active",
                        "packet_count": 4,
                        "byte_count": 1024,
                        "senders": ["192.168.1.1:5000"],
                        "sample_preview": "47 40 00 10",
                        "error": "",
                    }
                ],
            },
            "udp_capture_result": None,
            "traffic_capture_result": {
                "ok": True,
                "host": "192.168.1.1",
                "packet_count": 12,
                "protocol_counts": {"udp": 12},
                "hot_ports": [
                    {
                        "protocol": "udp",
                        "port": 8080,
                        "direction": "from_drone",
                        "packet_count": 8,
                        "sample_line": "IP 192.168.1.1.5000 > 192.168.1.2.8080: UDP, length 1316",
                    }
                ],
                "raw_preview": [
                    "IP 192.168.1.1.5000 > 192.168.1.2.8080: UDP, length 1316",
                ],
                "suggested_stream_url": "udp://@0.0.0.0:8080",
                "permission_required": False,
                "detail": "Captured traffic involving 192.168.1.1.",
            },
            "network_discovery_result": {
                "ok": True,
                "packet_count": 14,
                "likely_hosts": [
                    {
                        "host": "192.168.0.1",
                        "line_count": 8,
                        "source_count": 5,
                        "destination_count": 3,
                        "protocol_counts": {"arp": 2, "udp": 6},
                        "sample_line": "IP 192.168.0.1.5000 > 192.168.0.2.8080: UDP, length 1316",
                    }
                ],
                "raw_preview": [
                    "IP 192.168.0.1.5000 > 192.168.0.2.8080: UDP, length 1316",
                ],
                "suggested_wifi_host": "192.168.0.1",
                "permission_required": False,
                "detail": "Discovered private-network hosts during the capture window.",
            },
            "suggested_stream_url": "udp://@0.0.0.0:8080",
        }

    def probe(self, payload=None):
        return {
            "ok": True,
            "scheme": "udp",
            "host": "0.0.0.0",
            "port": 8080,
            "detail": "UDP targets usually cannot be verified with a simple socket probe.",
            "browser_support": "Use proxy mode.",
            "recommended_viewer_mode": "proxy",
            "host_matches_stream": True,
            "candidates": [
                {
                    "label": "UDP 8080",
                    "url": "udp://@0.0.0.0:8080",
                    "viewer_mode": "proxy",
                    "viewer_mode_label": "Proxy through this app",
                }
            ],
        }

    def scan_udp(self, payload=None):
        return {
            "ok": True,
            "capture_mode": "scan",
            "duration_seconds": 2.5,
            "active_port": 8080,
            "suggested_stream_url": "udp://@0.0.0.0:8080",
            "detail": "Detected UDP packets on port 8080.",
            "ports": [
                {
                    "port": 8080,
                    "status": "active",
                    "packet_count": 4,
                    "byte_count": 1024,
                    "senders": ["192.168.1.1:5000"],
                    "sample_preview": "47 40 00 10",
                    "error": "",
                }
            ],
        }

    def capture_udp(self, payload=None):
        return {
            "ok": True,
            "capture_mode": "capture",
            "duration_seconds": 5.0,
            "active_port": 8080,
            "suggested_stream_url": "udp://@0.0.0.0:8080",
            "detail": "Detected UDP packets on port 8080 during capture.",
            "ports": [
                {
                    "port": 8080,
                    "status": "active",
                    "packet_count": 9,
                    "byte_count": 2304,
                    "senders": ["192.168.1.1:5000"],
                    "sample_preview": "47 40 00 10",
                    "error": "",
                }
            ],
        }

    def capture_traffic(self, payload=None):
        return {
            "ok": True,
            "host": "192.168.1.1",
            "packet_count": 12,
            "protocol_counts": {"udp": 12},
            "hot_ports": [
                {
                    "protocol": "udp",
                    "port": 8080,
                    "direction": "from_drone",
                    "packet_count": 8,
                    "sample_line": "IP 192.168.1.1.5000 > 192.168.1.2.8080: UDP, length 1316",
                }
            ],
            "raw_preview": [
                "IP 192.168.1.1.5000 > 192.168.1.2.8080: UDP, length 1316",
            ],
            "suggested_stream_url": "udp://@0.0.0.0:8080",
            "permission_required": False,
            "detail": "Captured traffic involving 192.168.1.1.",
        }

    def discover_network(self):
        return {
            "ok": True,
            "packet_count": 14,
            "likely_hosts": [
                {
                    "host": "192.168.0.1",
                    "line_count": 8,
                    "source_count": 5,
                    "destination_count": 3,
                    "protocol_counts": {"arp": 2, "udp": 6},
                    "sample_line": "IP 192.168.0.1.5000 > 192.168.0.2.8080: UDP, length 1316",
                }
            ],
            "raw_preview": [
                "IP 192.168.0.1.5000 > 192.168.0.2.8080: UDP, length 1316",
            ],
            "suggested_wifi_host": "192.168.0.1",
            "permission_required": False,
            "detail": "Discovered private-network hosts during the capture window.",
        }

    def stop_stream(self):
        return None

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
            "DRONE_CAMERA_SETTINGS_PATH": tmp_path / "camera_settings.json",
            "CAMERA_SERVICE": StubCameraService(),
        }
    )
    return app.test_client()


def test_routes_and_camera_endpoints(tmp_path):
    client = build_client(tmp_path)

    assert client.get("/").status_code == 200
    assert client.get("/health").get_json()["status"] == "ok"
    assert client.get("/api/settings").get_json()["camera_name"] == "Bench Camera"

    update_response = client.post(
        "/api/settings",
        json={
            "camera_name": "Field Camera",
            "wifi_ssid": "HFUN_TEST",
            "wifi_host": "192.168.1.1",
            "viewer_mode": "proxy",
            "stream_url": "udp://@0.0.0.0:8080",
            "notes": "updated",
        },
    )
    assert update_response.status_code == 200
    assert update_response.get_json()["settings"]["camera_name"] == "Field Camera"

    status_response = client.get("/api/status")
    assert status_response.status_code == 200
    assert status_response.get_json()["proxy_ready"] is True

    probe_response = client.post("/api/probe", json={"stream_url": "udp://@0.0.0.0:8080"})
    assert probe_response.status_code == 200
    assert probe_response.get_json()["ok"] is True

    udp_scan_response = client.post("/api/udp-scan", json={"stream_url": "udp://@0.0.0.0:8080"})
    assert udp_scan_response.status_code == 200
    assert udp_scan_response.get_json()["active_port"] == 8080

    udp_capture_response = client.post("/api/udp-capture", json={"stream_url": "udp://@0.0.0.0:8080"})
    assert udp_capture_response.status_code == 200
    assert udp_capture_response.get_json()["capture_mode"] == "capture"

    traffic_capture_response = client.post("/api/traffic-capture", json={"wifi_host": "192.168.1.1"})
    assert traffic_capture_response.status_code == 200
    assert traffic_capture_response.get_json()["host"] == "192.168.1.1"

    network_discovery_response = client.post("/api/network-discovery")
    assert network_discovery_response.status_code == 200
    assert network_discovery_response.get_json()["suggested_wifi_host"] == "192.168.0.1"

    stream_response = client.get("/api/stream")
    assert stream_response.status_code == 200
    assert stream_response.mimetype == "multipart/x-mixed-replace"
    assert b"fakejpeg" in stream_response.data

    disconnect_response = client.post("/api/disconnect")
    assert disconnect_response.status_code == 200
    assert disconnect_response.get_json()["status"] == "success"
