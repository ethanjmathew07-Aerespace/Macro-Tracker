from __future__ import annotations

import json
import re
import selectors
import shutil
import socket
import subprocess
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
    "notes": "Start with the RTSP URL. If that fails, inspect the original vendor app traffic to discover the real stream path and port.",
}

DEFAULT_PORTS = {
    "rtsp": 554,
    "http": 80,
    "https": 443,
    "udp": 8080,
}

COMMON_UDP_PORTS = (8000, 8080, 8081, 8554, 8800, 8888, 8899, 9000)
UDP_LISTEN_HOST = "0.0.0.0"
UDP_STREAM_QUERY = "fifo_size=50000000&overrun_nonfatal=1"
TRAFFIC_CAPTURE_PACKET_LIMIT = 120
TRAFFIC_CAPTURE_DURATION_SECONDS = 6.0
NETWORK_DISCOVERY_PACKET_LIMIT = 180
NETWORK_DISCOVERY_DURATION_SECONDS = 6.0

DEFAULT_STREAM_CANDIDATES = (
    ("RTSP ch0", "rtsp://{host}:554/live/ch0", "proxy"),
    ("RTSP stream1", "rtsp://{host}:554/stream1", "proxy"),
    ("RTSP 8554", "rtsp://{host}:8554/live/ch0", "proxy"),
    ("UDP 8080", "udp://@0.0.0.0:8080", "proxy"),
    ("HTTP MJPEG", "http://{host}:8080/?action=stream", "direct_mjpeg"),
    ("HTTP MJPEG alt", "http://{host}:8080/stream.mjpg", "direct_mjpeg"),
    ("HTTP HLS", "http://{host}:8080/live.m3u8", "direct_video"),
)


class CameraValidationError(ValueError):
    """Raised when a drone camera payload is invalid."""


def _udp_listener_url(port: int) -> str:
    return f"udp://@{UDP_LISTEN_HOST}:{port}"


def _udp_stream_variants(port: int) -> list[str]:
    base = _udp_listener_url(port)
    return [
        base,
        f"{base}?{UDP_STREAM_QUERY}",
        f"udp://{UDP_LISTEN_HOST}:{port}",
        f"udp://{UDP_LISTEN_HOST}:{port}?{UDP_STREAM_QUERY}",
    ]


def _listener_host(host: str) -> bool:
    return host in {"", UDP_LISTEN_HOST, "127.0.0.1", "localhost"}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _recommended_viewer_mode(scheme: str) -> str:
    return "proxy" if scheme in {"rtsp", "udp"} else "direct_mjpeg"


def _viewer_mode_label(viewer_mode: str) -> str:
    labels = {
        "proxy": "Proxy through this app",
        "direct_mjpeg": "Direct MJPEG stream",
        "direct_video": "Direct browser video",
    }
    return labels.get(viewer_mode, viewer_mode)


def build_stream_candidates(hosts: list[str]) -> list[dict[str, str]]:
    candidate_list: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    normalized_hosts = _dedupe(hosts) or [DEFAULT_CAMERA_SETTINGS["wifi_host"]]
    for label, template, viewer_mode in DEFAULT_STREAM_CANDIDATES:
        target_hosts = normalized_hosts if "{host}" in template else [""]
        for host in target_hosts:
            url = template.format(host=host)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            candidate_list.append(
                {
                    "label": label,
                    "url": url,
                    "viewer_mode": viewer_mode,
                    "viewer_mode_label": _viewer_mode_label(viewer_mode),
                }
            )

    return candidate_list


def _udp_candidate_ports(current_port: int | None = None) -> list[int]:
    ports = [current_port] if current_port else []
    ports.extend(COMMON_UDP_PORTS)
    normalized: list[int] = []
    seen: set[int] = set()

    for port in ports:
        if not isinstance(port, int) or not (1 <= port <= 65535) or port in seen:
            continue
        seen.add(port)
        normalized.append(port)

    return normalized


def _normalize_udp_ports(ports: list[Any] | None) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()

    for value in ports or []:
        try:
            port = int(value)
        except (TypeError, ValueError):
            continue
        if not (1 <= port <= 65535) or port in seen:
            continue
        seen.add(port)
        normalized.append(port)

    return normalized


def _packet_preview(packet: bytes, *, limit: int = 18) -> str:
    if not packet:
        return ""
    head = packet[:limit]
    return " ".join(f"{byte:02x}" for byte in head)


def _packet_format_hint(packet: bytes) -> str:
    if not packet:
        return ""
    if packet[0] == 0x47:
        return "mpegts"
    if len(packet) >= 4 and packet[:4] in {b"\x00\x00\x00\x01", b"\x00\x00\x01\x67"}:
        return "h264_annexb"
    if len(packet) >= 2 and (packet[0] & 0xC0) == 0x80:
        return "possible_rtp"
    if packet.startswith(b"RIFF"):
        return "riff_container"
    return "unknown"


def _extract_ipv4_addresses(text: str) -> list[str]:
    matches = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    valid: list[str] = []
    for match in matches:
        octets = match.split(".")
        if all(part.isdigit() and 0 <= int(part) <= 255 for part in octets):
            valid.append(match)
    return valid


def _is_private_ipv4(host: str) -> bool:
    try:
        octets = [int(part) for part in host.split(".")]
    except ValueError:
        return False
    if len(octets) != 4:
        return False
    first, second, _, _ = octets
    if first == 10:
        return True
    if first == 172 and 16 <= second <= 31:
        return True
    if first == 192 and second == 168:
        return True
    return False


def _host_priority(host: str, summary: dict[str, Any]) -> tuple[int, int, int]:
    score = 0
    if host.endswith(".1"):
        score += 4
    if summary.get("source_count", 0) >= summary.get("destination_count", 0):
        score += 2
    score += min(summary.get("protocol_counts", {}).get("udp", 0), 5)
    score += min(summary.get("protocol_counts", {}).get("tcp", 0), 3)
    return (score, summary.get("line_count", 0), summary.get("source_count", 0))


def _parse_endpoint(endpoint: str) -> tuple[str, int | None]:
    value = endpoint.rstrip(":")
    if value.count(".") >= 1:
        host, _, maybe_port = value.rpartition(".")
        if maybe_port.isdigit():
            return host, int(maybe_port)
    return value, None


def _protocol_label(detail: str) -> str:
    upper_detail = detail.upper()
    if upper_detail.startswith("UDP"):
        return "udp"
    if upper_detail.startswith("ICMP"):
        return "icmp"
    if upper_detail.startswith("ARP"):
        return "arp"
    if upper_detail.startswith("IP6"):
        return "ipv6"
    if "FLAGS" in upper_detail or upper_detail.startswith("TCP"):
        return "tcp"
    return "other"


class UdpPacketScanner:
    def scan(self, ports: list[int], *, duration_seconds: float = 2.5, capture_mode: str = "scan") -> dict[str, Any]:
        requested_ports = _normalize_udp_ports(ports) or list(COMMON_UDP_PORTS)

        selector = selectors.DefaultSelector()
        sockets: list[socket.socket] = []
        observations: dict[int, dict[str, Any]] = {}

        for port in requested_ports:
            observation = {
                "port": port,
                "status": "idle",
                "packet_count": 0,
                "byte_count": 0,
                "senders": [],
                "sample_preview": "",
                "format_hint": "",
                "error": "",
            }
            observations[port] = observation

            try:
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                udp_socket.bind((UDP_LISTEN_HOST, port))
                udp_socket.setblocking(False)
                selector.register(udp_socket, selectors.EVENT_READ, port)
                sockets.append(udp_socket)
            except OSError as exc:
                observation["status"] = "bind_error"
                observation["error"] = str(exc)

        deadline = time.monotonic() + max(0.5, duration_seconds)
        try:
            while time.monotonic() < deadline and selector.get_map():
                timeout = min(0.25, max(0.0, deadline - time.monotonic()))
                events = selector.select(timeout)
                if not events:
                    continue

                for key, _ in events:
                    udp_socket = key.fileobj
                    port = key.data
                    observation = observations[port]

                    while True:
                        try:
                            packet, address = udp_socket.recvfrom(65535)
                        except BlockingIOError:
                            break
                        except OSError as exc:
                            observation["status"] = "socket_error"
                            observation["error"] = str(exc)
                            break

                        observation["status"] = "active"
                        observation["packet_count"] += 1
                        observation["byte_count"] += len(packet)
                        sender = f"{address[0]}:{address[1]}"
                        if sender not in observation["senders"] and len(observation["senders"]) < 4:
                            observation["senders"].append(sender)
                        if not observation["sample_preview"]:
                            observation["sample_preview"] = _packet_preview(packet)
                        if not observation["format_hint"]:
                            observation["format_hint"] = _packet_format_hint(packet)
        finally:
            for udp_socket in sockets:
                try:
                    selector.unregister(udp_socket)
                except Exception:
                    pass
                udp_socket.close()

        active_candidates = [item for item in observations.values() if item["packet_count"] > 0]
        active_candidates.sort(key=lambda item: (item["packet_count"], item["byte_count"]), reverse=True)
        active_port = active_candidates[0]["port"] if active_candidates else None

        if active_port is not None:
            detail = f"Detected UDP packets on port {active_port}. Proxy mode can listen on that port automatically."
        else:
            detail = (
                "No UDP packets were detected on the common listener ports during this scan. "
                "The drone may be idle, broadcasting on another port, or require a control wake-up sequence."
            )

        return {
            "ok": active_port is not None,
            "capture_mode": capture_mode,
            "duration_seconds": max(0.5, duration_seconds),
            "ports": [observations[port] for port in sorted(observations)],
            "active_port": active_port,
            "suggested_stream_url": _udp_listener_url(active_port) if active_port is not None else None,
            "detail": detail,
        }


class TcpdumpTrafficCapture:
    line_pattern = re.compile(r"^\S+\s+(?:IP6?|ARP)\s+(?P<src>\S+)\s+>\s+(?P<dst>\S+):\s+(?P<detail>.+)$")

    def capture(
        self,
        host: str,
        *,
        duration_seconds: float = TRAFFIC_CAPTURE_DURATION_SECONDS,
        packet_limit: int = TRAFFIC_CAPTURE_PACKET_LIMIT,
    ) -> dict[str, Any]:
        stdout_text, stderr_text, error_result = self._run_tcpdump(
            ["host", host],
            duration_seconds=duration_seconds,
            packet_limit=packet_limit,
            detail_scope="traffic capture",
        )
        if error_result is not None:
            return {
                **error_result,
                "host": host,
                "hot_ports": [],
                "suggested_stream_url": None,
            }

        lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
        protocol_counts: dict[str, int] = {}
        hot_ports: dict[tuple[str, int, str], dict[str, Any]] = {}
        raw_preview: list[str] = []

        for line in lines:
            if len(raw_preview) < 8:
                raw_preview.append(line)

            match = self.line_pattern.match(line)
            if not match:
                continue

            source = match.group("src")
            destination = match.group("dst")
            detail = match.group("detail")
            protocol = _protocol_label(detail)
            protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1

            source_host, source_port = _parse_endpoint(source)
            destination_host, destination_port = _parse_endpoint(destination)
            if source_host == host and destination_port is not None:
                key = (protocol, destination_port, "from_drone")
                record = hot_ports.setdefault(
                    key,
                    {
                        "protocol": protocol,
                        "port": destination_port,
                        "direction": "from_drone",
                        "packet_count": 0,
                        "sample_line": line,
                    },
                )
                record["packet_count"] += 1
            elif destination_host == host and destination_port is not None:
                key = (protocol, destination_port, "to_drone")
                record = hot_ports.setdefault(
                    key,
                    {
                        "protocol": protocol,
                        "port": destination_port,
                        "direction": "to_drone",
                        "packet_count": 0,
                        "sample_line": line,
                    },
                )
                record["packet_count"] += 1
            elif source_host == host and source_port is not None:
                key = (protocol, source_port, "from_drone")
                record = hot_ports.setdefault(
                    key,
                    {
                        "protocol": protocol,
                        "port": source_port,
                        "direction": "from_drone",
                        "packet_count": 0,
                        "sample_line": line,
                    },
                )
                record["packet_count"] += 1

        ordered_ports = sorted(
            hot_ports.values(),
            key=lambda item: (item["packet_count"], item["port"]),
            reverse=True,
        )

        suggested_stream_url = None
        for item in ordered_ports:
            if item["protocol"] == "udp" and item["direction"] == "from_drone":
                suggested_stream_url = _udp_listener_url(item["port"])
                break

        if ordered_ports:
            top = ordered_ports[0]
            detail = (
                f"Captured {len(lines)} packets involving {host}. "
                f"Top clue: {top['protocol'].upper()} traffic on port {top['port']} ({top['direction']})."
            )
        else:
            detail = (
                f"No traffic involving {host} was captured during the observation window. "
                "That usually means the drone is idle or using a link-level protocol we are not seeing yet."
            )

        return {
            "ok": bool(ordered_ports),
            "host": host,
            "packet_count": len(lines),
            "protocol_counts": protocol_counts,
            "hot_ports": ordered_ports[:10],
            "raw_preview": raw_preview,
            "suggested_stream_url": suggested_stream_url,
            "permission_required": False,
            "detail": detail,
        }

    def discover(
        self,
        *,
        duration_seconds: float = NETWORK_DISCOVERY_DURATION_SECONDS,
        packet_limit: int = NETWORK_DISCOVERY_PACKET_LIMIT,
    ) -> dict[str, Any]:
        stdout_text, stderr_text, error_result = self._run_tcpdump(
            ["arp", "or", "ip"],
            duration_seconds=duration_seconds,
            packet_limit=packet_limit,
            detail_scope="network discovery",
        )
        if error_result is not None:
            return {
                **error_result,
                "packet_count": 0,
                "likely_hosts": [],
                "raw_preview": [],
                "suggested_wifi_host": None,
            }

        lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
        host_summaries: dict[str, dict[str, Any]] = {}
        raw_preview: list[str] = []

        for line in lines:
            if len(raw_preview) < 10:
                raw_preview.append(line)

            match = self.line_pattern.match(line)
            protocol = "other"
            source_host = ""
            destination_host = ""

            if match:
                source = match.group("src")
                destination = match.group("dst")
                detail = match.group("detail")
                protocol = _protocol_label(detail)
                source_host, _ = _parse_endpoint(source)
                destination_host, _ = _parse_endpoint(destination)
            else:
                addresses = _extract_ipv4_addresses(line)
                if addresses:
                    source_host = addresses[0]
                    destination_host = addresses[1] if len(addresses) > 1 else ""
                protocol = "arp" if "ARP" in line.upper() else "other"

            for host, direction in ((source_host, "source_count"), (destination_host, "destination_count")):
                if not host or not _is_private_ipv4(host):
                    continue
                summary = host_summaries.setdefault(
                    host,
                    {
                        "host": host,
                        "line_count": 0,
                        "source_count": 0,
                        "destination_count": 0,
                        "protocol_counts": {},
                        "sample_line": line,
                    },
                )
                summary["line_count"] += 1
                summary[direction] += 1
                summary["protocol_counts"][protocol] = summary["protocol_counts"].get(protocol, 0) + 1

        likely_hosts = sorted(
            host_summaries.values(),
            key=lambda item: _host_priority(item["host"], item),
            reverse=True,
        )

        suggested_wifi_host = likely_hosts[0]["host"] if likely_hosts else None
        if likely_hosts:
            detail = (
                f"Discovered {len(likely_hosts)} private-network hosts during the capture window. "
                f"Top candidate: {suggested_wifi_host}."
            )
        else:
            detail = (
                "No private-network hosts were discovered during the capture window. "
                "The drone may be idle, on a different interface, or using a link-level protocol only."
            )

        return {
            "ok": bool(likely_hosts),
            "packet_count": len(lines),
            "likely_hosts": likely_hosts[:10],
            "raw_preview": raw_preview,
            "suggested_wifi_host": suggested_wifi_host,
            "permission_required": False,
            "detail": detail,
        }

    def _run_tcpdump(
        self,
        filter_parts: list[str],
        *,
        duration_seconds: float,
        packet_limit: int,
        detail_scope: str,
    ) -> tuple[str, str, dict[str, Any] | None]:
        tcpdump_path = shutil.which("tcpdump")
        if not tcpdump_path:
            return "", "", {
                "ok": False,
                "permission_required": False,
                "detail": f"tcpdump is not installed on this Mac, so {detail_scope} is unavailable.",
            }

        command = [tcpdump_path, "-nn", "-l", "-c", str(packet_limit), *filter_parts]
        stdout_text = ""
        stderr_text = ""

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(2.0, duration_seconds),
                check=False,
            )
            stdout_text = completed.stdout or ""
            stderr_text = completed.stderr or ""
        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout or ""
            stderr_text = exc.stderr or ""

        stderr_lower = stderr_text.lower()
        if "permission denied" in stderr_lower or "you don't have permission" in stderr_lower:
            return "", stderr_text, {
                "ok": False,
                "permission_required": True,
                "detail": f"{detail_scope.title()} needs elevated packet-capture permissions. Restart the app with sudo or run tcpdump manually.",
            }

        return stdout_text, stderr_text, None


def _normalize_text(value: Any, *, field_name: str, required: bool = False) -> str:
    normalized = str(value or "").strip()
    if required and not normalized:
        raise CameraValidationError(f"{field_name} is required.")
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
        raise CameraValidationError("stream_url must start with rtsp://, udp://, http://, or https://")

    if viewer_mode not in {"proxy", "direct_mjpeg", "direct_video"}:
        raise CameraValidationError("viewer_mode must be proxy, direct_mjpeg, or direct_video.")

    if parsed.scheme != "udp" and not parsed.hostname:
        raise CameraValidationError("stream_url must include a host name or IP address.")

    return {
        "camera_name": camera_name,
        "wifi_ssid": wifi_ssid,
        "wifi_host": wifi_host,
        "stream_url": stream_url,
        "viewer_mode": viewer_mode,
        "notes": notes,
    }


class JsonCameraSettingsStore:
    def __init__(self, path: str | Path):
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
    def __init__(self, stream_urls: list[str]):
        self.stream_urls = _dedupe(stream_urls)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._condition = threading.Condition()
        self._latest_frame: bytes | None = None
        self._last_error: str | None = None
        self._active_stream_url: str | None = None
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
            raise RuntimeError("OpenCV is not installed. Run `python3 -m pip install -r requirements.txt` in this project first.")

        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._last_error = None
        self._thread = threading.Thread(target=self._reader_loop, name="camera-stream-reader", daemon=True)
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

    def active_stream_url(self) -> str | None:
        with self._condition:
            return self._active_stream_url

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
        attempt_errors: list[str] = []

        for stream_url in self.stream_urls:
            if self._stop_event.is_set():
                return

            parsed = urlparse(stream_url)
            backend = cv2.CAP_FFMPEG if parsed.scheme in {"rtsp", "udp"} and hasattr(cv2, "CAP_FFMPEG") else cv2.CAP_ANY
            capture = cv2.VideoCapture(stream_url, backend)

            if not capture.isOpened():
                attempt_errors.append(f"{stream_url} could not be opened.")
                capture.release()
                continue

            with self._condition:
                self._active_stream_url = stream_url
                self._last_error = None
                self._condition.notify_all()

            try:
                failed_reads = 0
                received_frame = False

                while not self._stop_event.is_set():
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        failed_reads += 1
                        if failed_reads >= 15:
                            problem = (
                                f"{stream_url} opened but frames were not decoded."
                                if not received_frame
                                else f"Lost frames after connecting to {stream_url}."
                            )
                            attempt_errors.append(problem)
                            break
                        time.sleep(0.1)
                        continue

                    received_frame = True
                    failed_reads = 0
                    encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if not encoded_ok:
                        continue

                    with self._condition:
                        self._latest_frame = encoded.tobytes()
                        self._frame_number += 1
                        self._condition.notify_all()

                if received_frame:
                    if self._stop_event.is_set():
                        return
                    attempt_errors.append(f"Connection dropped while reading {stream_url}.")
            except Exception as exc:  # pragma: no cover
                attempt_errors.append(str(exc))
            finally:
                capture.release()

        with self._condition:
            self._active_stream_url = None
            self._last_error = (
                "No working stream was found. Tried: " + " ".join(attempt_errors)
                if attempt_errors
                else "No stream candidates were available."
            )
            self._condition.notify_all()


class CameraService:
    def __init__(self, settings_store: JsonCameraSettingsStore):
        self.settings_store = settings_store
        self._stream_lock = threading.Lock()
        self._udp_lock = threading.Lock()
        self._bridge: CameraStreamBridge | None = None
        self._bridge_url: str | None = None
        self._udp_scan_result: dict[str, Any] | None = None
        self._udp_capture_result: dict[str, Any] | None = None
        self._traffic_capture_result: dict[str, Any] | None = None
        self._network_discovery_result: dict[str, Any] | None = None
        self._detected_udp_stream_url: str | None = None

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
        opencv_available = CameraStreamBridge([settings["stream_url"]]).opencv_available()
        target_hosts = _dedupe([parsed.hostname or "", settings["wifi_host"]])
        (
            udp_scan_result,
            udp_capture_result,
            traffic_capture_result,
            network_discovery_result,
            detected_udp_stream_url,
        ) = self._udp_state()
        discovered_hosts = [
            item.get("host", "")
            for item in (network_discovery_result or {}).get("likely_hosts", [])
            if item.get("host")
        ]
        target_hosts = _dedupe([*discovered_hosts, parsed.hostname or "", settings["wifi_host"]])
        return {
            "settings": settings,
            "stream_scheme": parsed.scheme or "",
            "opencv_available": opencv_available,
            "proxy_ready": opencv_available and settings["viewer_mode"] == "proxy",
            "active_stream_url": self._bridge.active_stream_url() if self._bridge else None,
            "last_error": self._bridge.latest_error() if self._bridge else None,
            "viewer_hint": self._viewer_hint(settings["viewer_mode"], parsed.scheme or ""),
            "recommended_viewer_mode": _recommended_viewer_mode(parsed.scheme or ""),
            "connection_summary": self._connection_summary(settings, parsed.scheme or "", parsed.hostname or ""),
            "stream_candidates": build_stream_candidates(target_hosts),
            "host_matches_stream": self._host_matches_stream(parsed.scheme or "", parsed.hostname or "", settings["wifi_host"]),
            "udp_scan_result": udp_scan_result,
            "udp_capture_result": udp_capture_result,
            "traffic_capture_result": traffic_capture_result,
            "network_discovery_result": network_discovery_result,
            "suggested_stream_url": detected_udp_stream_url,
        }

    def open_stream(self):
        settings = self.get_settings()
        if settings["viewer_mode"] != "proxy":
            raise CameraValidationError("Proxy streaming is disabled for the current viewer mode.")

        bridge = self._get_bridge(settings["stream_url"])
        return bridge.stream_generator()

    def probe(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self.get_settings()
        normalized = normalize_camera_settings({**settings, **(payload or {})})
        parsed = urlparse(normalized["stream_url"])
        scheme = parsed.scheme
        host = parsed.hostname or ""
        port = parsed.port or DEFAULT_PORTS.get(scheme)
        target_hosts = _dedupe([host, normalized["wifi_host"]])
        host_matches_stream = (not host) or host == normalized["wifi_host"]

        if scheme == "udp":
            result = ProbeResult(
                ok=True,
                scheme=scheme,
                host=host or normalized["wifi_host"],
                port=port,
                detail=(
                    "UDP targets usually cannot be verified with a simple socket probe. "
                    "Run the UDP listener scan to see whether packets are actually arriving on common ports."
                ),
                browser_support="Browsers do not open raw UDP directly. Use proxy mode.",
            )
            return {
                **result.__dict__,
                "recommended_viewer_mode": _recommended_viewer_mode(scheme),
                "host_matches_stream": host_matches_stream,
                "candidates": build_stream_candidates(target_hosts),
            }

        if not host or port is None:
            result = ProbeResult(
                ok=False,
                scheme=scheme,
                host=host,
                port=port,
                detail="The stream URL is missing a host or port.",
                browser_support=self._browser_support_message(scheme),
            )
            return {
                **result.__dict__,
                "recommended_viewer_mode": _recommended_viewer_mode(scheme),
                "host_matches_stream": host_matches_stream,
                "candidates": build_stream_candidates(target_hosts),
            }

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
            detail=(
                detail
                if host_matches_stream
                else detail + " The stream URL host does not match the camera Wi-Fi host field."
            ),
            browser_support=self._browser_support_message(scheme),
        )
        return {
            **result.__dict__,
            "recommended_viewer_mode": _recommended_viewer_mode(scheme),
            "host_matches_stream": host_matches_stream,
            "candidates": build_stream_candidates(target_hosts),
        }

    def _get_bridge(self, stream_url: str) -> CameraStreamBridge:
        settings = self.get_settings()
        stream_urls = self._build_stream_urls(settings, stream_url)
        with self._stream_lock:
            primary_url = stream_urls[0]
            if self._bridge is None or self._bridge_url != primary_url:
                if self._bridge is not None:
                    self._bridge.stop()
                self._bridge = CameraStreamBridge(stream_urls)
                self._bridge_url = primary_url
            return self._bridge

    def _build_stream_urls(self, settings: dict[str, str], stream_url: str) -> list[str]:
        parsed = urlparse(stream_url)
        if parsed.scheme not in {"rtsp", "http", "https", "udp"}:
            return [stream_url]

        if parsed.scheme == "udp":
            udp_urls: list[str] = []
            for port in _udp_candidate_ports(parsed.port):
                udp_urls.extend(_udp_stream_variants(port))
            prioritized_url = self._detected_udp_stream_url
            prioritized_urls = _udp_stream_variants(urlparse(prioritized_url).port) if prioritized_url else []
            current_port = parsed.port
            current_urls = _udp_stream_variants(current_port) if current_port else [stream_url]
            return _dedupe([*prioritized_urls, *current_urls, stream_url, *udp_urls])

        target_hosts = _dedupe([parsed.hostname or "", settings["wifi_host"]])
        candidates = build_stream_candidates(target_hosts)
        candidate_urls = [candidate["url"] for candidate in candidates if urlparse(candidate["url"]).scheme == parsed.scheme]
        return _dedupe([stream_url, *candidate_urls])

    def scan_udp(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._run_udp_observation(payload, duration_seconds=2.5, capture_mode="scan")
        with self._udp_lock:
            self._udp_scan_result = result
            if result["suggested_stream_url"]:
                self._detected_udp_stream_url = result["suggested_stream_url"]
        return result

    def capture_udp(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._run_udp_observation(payload, duration_seconds=5.0, capture_mode="capture")
        with self._udp_lock:
            self._udp_capture_result = result
            if result["suggested_stream_url"]:
                self._detected_udp_stream_url = result["suggested_stream_url"]
        return result

    def capture_traffic(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self.get_settings()
        normalized = normalize_camera_settings({**settings, **(payload or {})})
        capture = TcpdumpTrafficCapture().capture(normalized["wifi_host"])
        with self._udp_lock:
            self._traffic_capture_result = capture
            if capture.get("suggested_stream_url"):
                self._detected_udp_stream_url = capture["suggested_stream_url"]
        return capture

    def discover_network(self) -> dict[str, Any]:
        discovery = TcpdumpTrafficCapture().discover()
        with self._udp_lock:
            self._network_discovery_result = discovery
        return discovery

    def _run_udp_observation(
        self,
        payload: dict[str, Any] | None,
        *,
        duration_seconds: float,
        capture_mode: str,
    ) -> dict[str, Any]:
        settings = self.get_settings()
        normalized = normalize_camera_settings({**settings, **(payload or {})})
        parsed = urlparse(normalized["stream_url"])
        ports = _udp_candidate_ports(parsed.port if parsed.scheme == "udp" else None)
        scanner = UdpPacketScanner()
        result = scanner.scan(ports, duration_seconds=duration_seconds, capture_mode=capture_mode)
        result["current_stream_url"] = normalized["stream_url"]
        result["current_port"] = parsed.port if parsed.scheme == "udp" else None
        return result

    def _udp_state(
        self,
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
        str | None,
    ]:
        with self._udp_lock:
            return (
                self._udp_scan_result,
                self._udp_capture_result,
                self._traffic_capture_result,
                self._network_discovery_result,
                self._detected_udp_stream_url,
            )

    def _host_matches_stream(self, scheme: str, stream_host: str, wifi_host: str) -> bool:
        if not stream_host:
            return True
        if scheme == "udp" and _listener_host(stream_host):
            return True
        return stream_host == wifi_host

    def _connection_summary(self, settings: dict[str, str], scheme: str, stream_host: str) -> str:
        if stream_host and not self._host_matches_stream(scheme, stream_host, settings["wifi_host"]):
            return (
                "The stream URL points to a different host than the saved camera Wi-Fi target. "
                "That is fine if the camera rebroadcasts video through another device, but verify the IP carefully."
            )
        if scheme == "rtsp":
            return "RTSP drone feeds are best opened in proxy mode so this computer handles decoding and your browser only receives JPEG frames."
        if scheme == "udp":
            (
                udp_scan_result,
                udp_capture_result,
                traffic_capture_result,
                network_discovery_result,
                detected_udp_stream_url,
            ) = self._udp_state()
            best_result = udp_capture_result or udp_scan_result or {}
            active_port = best_result.get("active_port")
            format_hint = ""
            if active_port:
                for item in best_result.get("ports", []):
                    if item.get("port") == active_port:
                        format_hint = item.get("format_hint") or ""
                        break
            if active_port:
                return (
                    f"UDP packets were detected on port {active_port}. Proxy mode will prioritize "
                    f"{detected_udp_stream_url or _udp_listener_url(active_port)} when you open the live feed."
                    + (f" Packet hint: {format_hint}." if format_hint else "")
                )
            hot_ports = (traffic_capture_result or {}).get("hot_ports", [])
            if hot_ports:
                top = hot_ports[0]
                return (
                    f"Capture mode saw {top['protocol'].upper()} traffic on port {top['port']} "
                    f"({top['direction']}). Adjust the stream target based on that clue."
                )
            likely_hosts = (network_discovery_result or {}).get("likely_hosts", [])
            if likely_hosts:
                return f"Network discovery found likely device hosts. Top candidate: {likely_hosts[0]['host']}."
            return "UDP feeds almost always need proxy mode because browsers cannot open the raw transport directly."
        return "HTTP camera feeds can work directly in the browser, but proxy mode is still useful when the camera behaves inconsistently."

    def _viewer_hint(self, viewer_mode: str, scheme: str) -> str:
        if viewer_mode == "proxy":
            if scheme == "rtsp":
                return "Recommended for RTSP and raw Wi-Fi drone feeds. This app decodes frames locally on this Mac and renders them in the app."
            if scheme == "udp":
                udp_scan_result, udp_capture_result, traffic_capture_result, network_discovery_result, _ = self._udp_state()
                active_port = (udp_scan_result or {}).get("active_port") or (udp_capture_result or {}).get("active_port")
                if active_port:
                    return f"UDP packets were seen on port {active_port}. Open the live feed to let the Mac bind to that listener automatically."
                hot_ports = (traffic_capture_result or {}).get("hot_ports", [])
                if hot_ports:
                    top = hot_ports[0]
                    return f"Traffic capture saw {top['protocol'].upper()} activity on port {top['port']}. Use that clue to choose the next stream target."
                likely_hosts = (network_discovery_result or {}).get("likely_hosts", [])
                if likely_hosts:
                    return f"Network discovery found likely device hosts. Start with {likely_hosts[0]['host']} as the camera IP."
            return "Proxy mode keeps the camera connection on this Mac and converts the stream into browser-friendly JPEG frames locally."
        if viewer_mode == "direct_mjpeg":
            return "Use direct MJPEG only if the camera already exposes an HTTP image stream."
        return "Use direct video only for browser-native HTTP formats like HLS."

    def _browser_support_message(self, scheme: str) -> str:
        if scheme == "rtsp":
            return "Browsers usually cannot play RTSP directly. Proxy mode is the safe default."
        if scheme == "udp":
            return "Browsers do not play raw UDP directly. Proxy mode is required."
        return "HTTP streams can sometimes be opened directly if the camera exposes MJPEG or HLS."
