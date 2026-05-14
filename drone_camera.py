from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_CAMERA_SETTINGS = {
    "camera_name": "Repurposed Drone Camera",
    "wifi_ssid": "",
    "wifi_host": "192.168.1.1",
    "stream_url": "rtsp://192.168.1.1:554/live/ch0",
    "viewer_mode": "proxy",
    "notes": "Start with the RTSP URL. If the feed does not appear, inspect the original app traffic to confirm the real stream path and port.",
}

DEFAULT_PORTS = {
    "rtsp": 554,
    "http": 80,
    "https": 443,
    "udp": 8080,
}


class DroneCameraValidationError(ValueError):
    """Raised when a drone camera request payload is invalid."""


def _normalize_text(value: Any, *, field_name: str, required: bool = False) -> str:
    normalized = str(value or "").strip()
    if required and not normalized:
        raise DroneCameraValidationError(f"{field_name} is required.")
    return normalized


def normalize_camera_settings(payload: dict[str, Any]) -> dict[str, str]:
    camera_name = _normalize_text(
        payload.get("camera_name", DEFAULT_CAMERA_SETTINGS["camera_name"]),
        field_name="camera_name",
        required=True,
    )
    wifi_ssid = _normalize_text(payload.get("wifi_ssid", DEFAULT_CAMERA_SETTINGS["wifi_ssid"]), field_name="wifi_ssid")
    wifi_host = _normalize_text(
        payload.get("wifi_host", DEFAULT_CAMERA_SETTINGS["wifi_host"]),
        field_name="wifi_host",
        required=True,
    )
    stream_url = _normalize_text(
        payload.get("stream_url", DEFAULT_CAMERA_SETTINGS["stream_url"]),
        field_name="stream_url",
        required=True,
    )
    notes = _normalize_text(payload.get("notes", DEFAULT_CAMERA_SETTINGS["notes"]), field_name="notes")
    viewer_mode = _normalize_text(
        payload.get("viewer_mode", DEFAULT_CAMERA_SETTINGS["viewer_mode"]),
        field_name="viewer_mode",
        required=True,
    )

    parsed = urlparse(stream_url)
    if parsed.scheme not in {"rtsp", "udp", "http", "https"}:
        raise DroneCameraValidationError("stream_url must start with rtsp://, udp://, http://, or https://")

    if viewer_mode not in {"proxy", "direct_mjpeg", "direct_video"}:
        raise DroneCameraValidationError("viewer_mode must be proxy, direct_mjpeg, or direct_video.")

    if parsed.scheme != "udp" and not parsed.hostname:
        raise DroneCameraValidationError("stream_url must include a host name or IP address.")

    return {
        "camera_name": camera_name,
        "wifi_ssid": wifi_ssid,
        "wifi_host": wifi_host,
        "stream_url": stream_url,
        "viewer_mode": viewer_mode,
        "notes": notes,
    }


class JsonCameraSettingsStore:
    def __init__(self, path: str | Path = "drone_camera_settings.json"):
        self.path = Path(path)
        self._lock = threading.Lock()

    def initialize(self) -> None:
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.save(DEFAULT_CAMERA_SETTINGS)

    def load(self) -> dict[str, str]:
        self.initialize()
        with self._lock:
            raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw or "{}")
        return {**DEFAULT_CAMERA_SETTINGS, **normalize_camera_settings(data)}

    def save(self, settings: dict[str, Any]) -> dict[str, str]:
        normalized = normalize_camera_settings(settings)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
        return normalized


@dataclass
class ProbeResult:
    ok: bool
    scheme: str
    host: str
    port: int | None
    detail: str
    browser_support: str


class CameraStreamBridge:
    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._condition = threading.Condition()
        self._latest_frame: bytes | None = None
        self._last_error: str | None = None
        self._frame_number = 0
        self._client_count = 0

    def opencv_available(self) -> bool:
        try:
            import cv2  # noqa: F401
        except ImportError:
            return False
        return True

    def start(self) -> None:
        if not self.opencv_available():
            raise RuntimeError("OpenCV is not installed. Run `python3 -m pip install -r requirements.txt` first.")

        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._last_error = None
        self._thread = threading.Thread(target=self._reader_loop, name="drone-camera-stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()

    def attach_client(self) -> None:
        with self._condition:
            self._client_count += 1

    def detach_client(self) -> None:
        with self._condition:
            self._client_count = max(0, self._client_count - 1)
            should_stop = self._client_count == 0
        if should_stop:
            self.stop()

    def latest_error(self) -> str | None:
        with self._condition:
            return self._last_error

    def stream_generator(self):
        self.start()
        self.attach_client()
        last_seen = -1

        try:
            while not self._stop_event.is_set():
                with self._condition:
                    self._condition.wait_for(
                        lambda: self._stop_event.is_set() or self._frame_number != last_seen or self._last_error is not None,
                        timeout=10,
                    )

                    if self._last_error and self._latest_frame is None:
                        raise RuntimeError(self._last_error)

                    if self._latest_frame is None or self._frame_number == last_seen:
                        continue

                    frame = self._latest_frame
                    last_seen = self._frame_number

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-store\r\n\r\n" + frame + b"\r\n"
                )
        finally:
            self.detach_client()

    def _reader_loop(self) -> None:
        import cv2

        capture = cv2.VideoCapture(self.stream_url)
        if not capture.isOpened():
            with self._condition:
                self._last_error = f"Could not open stream: {self.stream_url}"
                self._condition.notify_all()
            return

        try:
            failed_reads = 0
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    failed_reads += 1
                    if failed_reads >= 15:
                        with self._condition:
                            self._last_error = (
                                "The camera stream connected but frames were not decoded. "
                                "Double-check the stream path, protocol, and codec."
                            )
                            self._condition.notify_all()
                        return
                    time.sleep(0.1)
                    continue

                failed_reads = 0
                encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not encoded_ok:
                    continue

                with self._condition:
                    self._latest_frame = encoded.tobytes()
                    self._frame_number += 1
                    self._condition.notify_all()
        except Exception as exc:  # pragma: no cover
            with self._condition:
                self._last_error = str(exc)
                self._condition.notify_all()
        finally:
            capture.release()


class DroneCameraService:
    def __init__(self, settings_store: JsonCameraSettingsStore):
        self.settings_store = settings_store
        self._stream_lock = threading.Lock()
        self._bridge: CameraStreamBridge | None = None
        self._bridge_url: str | None = None

    def get_settings(self) -> dict[str, str]:
        return self.settings_store.load()

    def update_settings(self, payload: dict[str, Any]) -> dict[str, str]:
        existing = self.get_settings()
        normalized = normalize_camera_settings({**existing, **payload})
        settings = self.settings_store.save(normalized)
        self.stop_stream()
        return settings

    def stop_stream(self) -> None:
        with self._stream_lock:
            if self._bridge is not None:
                self._bridge.stop()
            self._bridge = None
            self._bridge_url = None

    def get_status(self) -> dict[str, Any]:
        settings = self.get_settings()
        parsed = urlparse(settings["stream_url"])
        opencv_available = CameraStreamBridge(settings["stream_url"]).opencv_available()
        return {
            "settings": settings,
            "stream_scheme": parsed.scheme or "",
            "opencv_available": opencv_available,
            "proxy_ready": opencv_available and settings["viewer_mode"] == "proxy",
            "active_stream_url": self._bridge_url,
            "last_error": self._bridge.latest_error() if self._bridge else None,
            "viewer_hint": self._viewer_hint(settings["viewer_mode"], parsed.scheme or ""),
        }

    def open_stream(self):
        settings = self.get_settings()
        if settings["viewer_mode"] != "proxy":
            raise DroneCameraValidationError("Proxy streaming is disabled for the current viewer mode.")

        bridge = self._get_bridge(settings["stream_url"])
        return bridge.stream_generator()

    def probe(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self.get_settings()
        normalized = normalize_camera_settings({**settings, **(payload or {})})
        parsed = urlparse(normalized["stream_url"])
        scheme = parsed.scheme
        host = parsed.hostname or ""
        port = parsed.port or DEFAULT_PORTS.get(scheme)

        if scheme == "udp":
            result = ProbeResult(
                ok=True,
                scheme=scheme,
                host=host or normalized["wifi_host"],
                port=port,
                detail="UDP targets usually cannot be confirmed with a simple socket test. If the proxy fails, sniff live traffic while the original app is open.",
                browser_support="Browsers do not open raw UDP streams directly. Use proxy mode.",
            )
            return result.__dict__

        if not host or port is None:
            result = ProbeResult(
                ok=False,
                scheme=scheme,
                host=host,
                port=port,
                detail="The stream URL is missing a host or port.",
                browser_support=self._browser_support_message(scheme),
            )
            return result.__dict__

        try:
            with socket.create_connection((host, port), timeout=2):
                detail = f"Reached {host}:{port} successfully."
                ok = True
        except OSError as exc:
            detail = f"Could not reach {host}:{port}: {exc}"
            ok = False

        result = ProbeResult(
            ok=ok,
            scheme=scheme,
            host=host,
            port=port,
            detail=detail,
            browser_support=self._browser_support_message(scheme),
        )
        return result.__dict__

    def _get_bridge(self, stream_url: str) -> CameraStreamBridge:
        with self._stream_lock:
            if self._bridge is None or self._bridge_url != stream_url:
                if self._bridge is not None:
                    self._bridge.stop()
                self._bridge = CameraStreamBridge(stream_url)
                self._bridge_url = stream_url
            return self._bridge

    def _viewer_hint(self, viewer_mode: str, scheme: str) -> str:
        if viewer_mode == "proxy":
            if scheme == "rtsp":
                return "Recommended for RTSP and raw Wi-Fi drone feeds. This app decodes frames and serves them to your phone."
            return "Proxy mode keeps the camera connection on this server and forwards browser-friendly JPEG frames to your phone."
        if viewer_mode == "direct_mjpeg":
            return "Use direct MJPEG only if the camera already exposes an HTTP image stream."
        return "Use direct video only for browser-native formats like HLS over HTTP."

    def _browser_support_message(self, scheme: str) -> str:
        if scheme == "rtsp":
            return "Browsers on phones usually cannot play RTSP directly. Proxy mode is the safe default."
        if scheme == "udp":
            return "Browsers do not play raw UDP directly. Proxy mode is required."
        return "HTTP streams can sometimes be opened directly if the camera exposes MJPEG or HLS."
