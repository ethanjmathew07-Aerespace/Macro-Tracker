from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

from drone_camera import (
    DroneCameraService,
    DroneCameraValidationError,
    JsonCameraSettingsStore,
)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    root_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(root_dir / "drone_cam_templates"),
        static_folder=str(root_dir / "drone_cam_static"),
        static_url_path="/static",
    )

    settings_path = Path(
        os.getenv("DRONE_CAMERA_SETTINGS_PATH", str(root_dir / "drone_camera_settings.json"))
    ).expanduser()
    app.config.from_mapping(DRONE_CAMERA_SETTINGS_PATH=settings_path)
    if test_config:
        app.config.update(test_config)

    settings_store = app.config.get("DRONE_CAMERA_SETTINGS_STORE")
    if settings_store is None:
        settings_store = JsonCameraSettingsStore(app.config["DRONE_CAMERA_SETTINGS_PATH"])
        settings_store.initialize()

    service = app.config.get("DRONE_CAMERA_SERVICE")
    if service is None:
        service = DroneCameraService(settings_store)

    app.extensions["drone_camera_service"] = service

    def get_drone_camera_service() -> DroneCameraService:
        return app.extensions["drone_camera_service"]

    @app.errorhandler(DroneCameraValidationError)
    def handle_validation_error(error: DroneCameraValidationError):
        return jsonify({"error": str(error)}), 400

    @app.route("/")
    def index():
        service = get_drone_camera_service()
        return render_template(
            "index.html",
            page_title="Drone Camera",
            camera_settings=service.get_settings(),
            camera_status=service.get_status(),
        )

    @app.get("/api/settings")
    def api_settings():
        return jsonify(get_drone_camera_service().get_settings())

    @app.post("/api/settings")
    def api_update_settings():
        payload = request.get_json(silent=True) or {}
        settings = get_drone_camera_service().update_settings(payload)
        return jsonify({"status": "success", "settings": settings})

    @app.get("/api/status")
    def api_status():
        return jsonify(get_drone_camera_service().get_status())

    @app.post("/api/probe")
    def api_probe():
        payload = request.get_json(silent=True) or {}
        return jsonify(get_drone_camera_service().probe(payload))

    @app.post("/api/disconnect")
    def api_disconnect():
        get_drone_camera_service().stop_stream()
        return jsonify({"status": "success"})

    @app.get("/api/stream")
    def api_stream():
        try:
            generator = get_drone_camera_service().open_stream()
        except (DroneCameraValidationError, RuntimeError) as error:
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
    port = int(os.getenv("PORT", "5501"))
    app.run(debug=debug, host=host, port=port)
