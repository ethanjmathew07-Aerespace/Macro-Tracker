from drone_camera_connect.camera_service import CameraService, JsonCameraSettingsStore


def test_udp_scan_prioritizes_detected_port(tmp_path, monkeypatch):
    store = JsonCameraSettingsStore(tmp_path / "camera_settings.json")
    store.initialize()
    store.save(
        {
            "camera_name": "Bench Camera",
            "wifi_ssid": "HK55DRONE-7145CC",
            "wifi_host": "192.168.1.1",
            "stream_url": "udp://@0.0.0.0:8080",
            "viewer_mode": "proxy",
            "notes": "test profile",
        }
    )
    service = CameraService(store)

    monkeypatch.setattr(
        "drone_camera_connect.camera_service.UdpPacketScanner.scan",
        lambda self, ports, duration_seconds=2.5, capture_mode="scan": {
            "ok": True,
            "capture_mode": capture_mode,
            "duration_seconds": duration_seconds,
            "active_port": 8899,
            "suggested_stream_url": "udp://@0.0.0.0:8899",
            "detail": "Detected UDP packets on port 8899.",
            "ports": [
                {
                    "port": 8899,
                    "status": "active",
                    "packet_count": 3,
                    "byte_count": 768,
                    "senders": ["192.168.1.1:5000"],
                    "sample_preview": "47 40 11 22",
                    "error": "",
                }
            ],
        },
    )

    result = service.scan_udp({"stream_url": "udp://@0.0.0.0:8080"})
    urls = service._build_stream_urls(service.get_settings(), "udp://@0.0.0.0:8080")
    status = service.get_status()

    assert result["active_port"] == 8899
    assert urls[0] == "udp://@0.0.0.0:8899"
    assert status["suggested_stream_url"] == "udp://@0.0.0.0:8899"
    assert status["udp_scan_result"]["active_port"] == 8899


def test_traffic_capture_updates_udp_suggestion(tmp_path, monkeypatch):
    store = JsonCameraSettingsStore(tmp_path / "camera_settings.json")
    store.initialize()
    service = CameraService(store)

    monkeypatch.setattr(
        "drone_camera_connect.camera_service.TcpdumpTrafficCapture.capture",
        lambda self, host, duration_seconds=6.0, packet_limit=120: {
            "ok": True,
            "host": host,
            "packet_count": 16,
            "protocol_counts": {"udp": 16},
            "hot_ports": [
                {
                    "protocol": "udp",
                    "port": 8899,
                    "direction": "from_drone",
                    "packet_count": 10,
                    "sample_line": "IP 192.168.1.1.5000 > 192.168.1.2.8899: UDP, length 1316",
                }
            ],
            "raw_preview": ["IP 192.168.1.1.5000 > 192.168.1.2.8899: UDP, length 1316"],
            "suggested_stream_url": "udp://@0.0.0.0:8899",
            "permission_required": False,
            "detail": "Captured traffic involving 192.168.1.1.",
        },
    )

    result = service.capture_traffic({"wifi_host": "192.168.1.1"})
    status = service.get_status()

    assert result["suggested_stream_url"] == "udp://@0.0.0.0:8899"
    assert status["traffic_capture_result"]["hot_ports"][0]["port"] == 8899
    assert status["suggested_stream_url"] == "udp://@0.0.0.0:8899"


def test_network_discovery_surfaces_likely_host(tmp_path, monkeypatch):
    store = JsonCameraSettingsStore(tmp_path / "camera_settings.json")
    store.initialize()
    service = CameraService(store)

    monkeypatch.setattr(
        "drone_camera_connect.camera_service.TcpdumpTrafficCapture.discover",
        lambda self, duration_seconds=6.0, packet_limit=180: {
            "ok": True,
            "packet_count": 20,
            "likely_hosts": [
                {
                    "host": "192.168.0.1",
                    "line_count": 10,
                    "source_count": 6,
                    "destination_count": 4,
                    "protocol_counts": {"arp": 2, "udp": 8},
                    "sample_line": "IP 192.168.0.1.5000 > 192.168.0.2.8080: UDP, length 1316",
                }
            ],
            "raw_preview": ["IP 192.168.0.1.5000 > 192.168.0.2.8080: UDP, length 1316"],
            "suggested_wifi_host": "192.168.0.1",
            "permission_required": False,
            "detail": "Discovered private-network hosts during the capture window.",
        },
    )

    result = service.discover_network()
    status = service.get_status()

    assert result["suggested_wifi_host"] == "192.168.0.1"
    assert status["network_discovery_result"]["likely_hosts"][0]["host"] == "192.168.0.1"
    assert any(candidate["url"].startswith("rtsp://192.168.0.1") for candidate in status["stream_candidates"])
