from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from flask import Flask, Response, jsonify, render_template, request

try:
    from drone_camera_connect.camera_service import (
        CameraService,
        CameraValidationError,
        JsonCameraSettingsStore,
    )
except ModuleNotFoundError:  # pragma: no cover - allows `python3 app.py` from the project directory.
    from camera_service import CameraService, CameraValidationError, JsonCameraSettingsStore

def _build_access_urls(host_url: str) -> list[str]:
    parsed = urlsplit(host_url)
    port = f":{parsed.port}" if parsed.port else ""
    candidates = ["127.0.0.1", "localhost", parsed.hostname or "127.0.0.1"]
    urls: list[str] = []
    seen: set[str] = set()

    for host in candidates:
        normalized_host = str(host).strip()
        if not normalized_host or normalized_host in seen:
            continue
        seen.add(normalized_host)
        urls.append(urlunsplit((parsed.scheme or "http", f"{normalized_host}{port}", "", "", "")))

    return urls


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    project_root = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
        static_url_path="/static",
    )

    settings_path = Path(
        os.getenv("DRONE_CAMERA_SETTINGS_PATH", str(project_root / "data" / "camera_settings.json"))
    ).expanduser()
    app.config.from_mapping(
        DRONE_CAMERA_SETTINGS_PATH=settings_path,
        APP_NAME="Drone Camera Connect",
    )
    if test_config:
        app.config.update(test_config)

    settings_store = app.config.get("SETTINGS_STORE")
    if settings_store is None:
        settings_store = JsonCameraSettingsStore(app.config["DRONE_CAMERA_SETTINGS_PATH"])
        settings_store.initialize()

    camera_service = app.config.get("CAMERA_SERVICE")
    if camera_service is None:
        camera_service = CameraService(settings_store)

    app.extensions["camera_service"] = camera_service

    def get_camera_service() -> CameraService:
        return app.extensions["camera_service"]

    @app.errorhandler(CameraValidationError)
    def handle_validation_error(error: CameraValidationError):
        return jsonify({"error": str(error)}), 400

    @app.get("/")
    def index():
        service = get_camera_service()
        return render_template(
            "index.html",
            page_title="Drone Camera Connect",
            app_name=app.config["APP_NAME"],
            camera_settings=service.get_settings(),
            camera_status=service.get_status(),
            access_urls=_build_access_urls(request.host_url),
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/settings")
    def api_settings():
        return jsonify(get_camera_service().get_settings())

    @app.post("/api/settings")
    def api_update_settings():
        payload = request.get_json(silent=True) or {}
        settings = get_camera_service().update_settings(payload)
        return jsonify({"status": "success", "settings": settings})

    @app.get("/api/status")
    def api_status():
        return jsonify(get_camera_service().get_status())

    @app.post("/api/probe")
    def api_probe():
        payload = request.get_json(silent=True) or {}
        return jsonify(get_camera_service().probe(payload))

    @app.post("/api/udp-scan")
    def api_udp_scan():
        payload = request.get_json(silent=True) or {}
        return jsonify(get_camera_service().scan_udp(payload))

    @app.post("/api/udp-capture")
    def api_udp_capture():
        payload = request.get_json(silent=True) or {}
        return jsonify(get_camera_service().capture_udp(payload))

    @app.post("/api/traffic-capture")
    def api_traffic_capture():
        payload = request.get_json(silent=True) or {}
        return jsonify(get_camera_service().capture_traffic(payload))

    @app.post("/api/network-discovery")
    def api_network_discovery():
        return jsonify(get_camera_service().discover_network())

    @app.post("/api/disconnect")
    def api_disconnect():
        get_camera_service().stop_stream()
        return jsonify({"status": "success"})

    @app.get("/api/stream")
    def api_stream():
        try:
            generator = get_camera_service().open_stream()
        except (CameraValidationError, RuntimeError) as error:
            return str(error), 503

        return Response(
            generator,
            mimetype="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1").lower() not in {"0", "false", "no", "off"}
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5601"))
    app.run(debug=debug, host=host, port=port)
