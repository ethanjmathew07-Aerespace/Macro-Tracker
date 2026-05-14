from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from simulator import (
    available_presets_payload,
    build_config_from_mapping,
    compare_results,
    run_simulation,
    save_report_bundle,
    serialize_config,
    serialize_result,
)


BASE_DIR = Path(__file__).resolve().parent
REPORT_ROOT = BASE_DIR / "reports"

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/presets")
def presets() -> object:
    return jsonify(available_presets_payload())


@app.post("/api/simulate")
def simulate() -> object:
    payload = request.get_json(force=True, silent=False) or {}
    controller = payload.get("controller", "both")
    config = build_config_from_mapping(payload)
    results = run_simulation(config, controller)
    return jsonify(
        {
            "config": serialize_config(config),
            "comparison": compare_results(results),
            "results": {name: serialize_result(result) for name, result in results.items()},
        }
    )


@app.post("/api/report")
def report() -> object:
    payload = request.get_json(force=True, silent=False) or {}
    controller = payload.get("controller", "both")
    config = build_config_from_mapping(payload)
    results = run_simulation(config, controller)
    folder = save_report_bundle(results, config, root=REPORT_ROOT)
    relative_folder = folder.relative_to(REPORT_ROOT)
    return jsonify(
        {
            "report_folder": str(folder),
            "assets": {
                "csv_url": f"/reports/{relative_folder}/results.csv",
                "plot_url": f"/reports/{relative_folder}/response.png",
                "summary_json_url": f"/reports/{relative_folder}/summary.json",
                "summary_txt_url": f"/reports/{relative_folder}/summary.txt",
            },
        }
    )


@app.get("/reports/<path:relative_path>")
def reports(relative_path: str) -> object:
    resolved = (REPORT_ROOT / relative_path).resolve()
    if REPORT_ROOT.resolve() not in resolved.parents and resolved != REPORT_ROOT.resolve():
        return jsonify({"error": "Invalid report path"}), 404
    if not resolved.exists() or not resolved.is_file():
        return jsonify({"error": "File not found"}), 404
    return send_file(resolved)


def main() -> None:
    host = os.getenv("ALTITUDE_SIMULATOR_HOST", "127.0.0.1")
    port = int(os.getenv("ALTITUDE_SIMULATOR_PORT", "5011"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
