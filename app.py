from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for

from fast_food_service import FastFoodService
from smart_food import NutritionLabelService, SmartFoodService
from storage import SQLiteRepository, ValidationError, parse_date


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)

    root_dir = Path(__file__).resolve().parent
    database_path = Path(os.getenv("DATABASE_PATH", str(root_dir / "macro_tracker.db"))).expanduser()
    legacy_json_path = Path(os.getenv("LEGACY_JSON_PATH", str(root_dir / "macros.json"))).expanduser()
    app.config.from_mapping(
        DATABASE_PATH=database_path,
        LEGACY_JSON_PATH=legacy_json_path,
        OCR_SWIFT_SCRIPT=root_dir / "scripts" / "ocr_label.swift",
    )
    if test_config:
        app.config.update(test_config)

    repository = app.config.get("REPOSITORY")
    if repository is None:
        repository = SQLiteRepository(
            db_path=app.config["DATABASE_PATH"],
            legacy_json_path=app.config["LEGACY_JSON_PATH"],
        )
        repository.initialize()

    fast_food_service = app.config.get("FAST_FOOD_SERVICE")
    if fast_food_service is None:
        fast_food_service = FastFoodService(repository)

    smart_food_service = app.config.get("SMART_FOOD_SERVICE")
    if smart_food_service is None:
        smart_food_service = SmartFoodService()

    label_service = app.config.get("LABEL_SERVICE")
    if label_service is None:
        label_service = NutritionLabelService(swift_script_path=app.config["OCR_SWIFT_SCRIPT"])

    app.extensions["macro_tracker_repository"] = repository
    app.extensions["macro_tracker_fast_food_service"] = fast_food_service
    app.extensions["macro_tracker_smart_food_service"] = smart_food_service
    app.extensions["macro_tracker_label_service"] = label_service

    def get_repository() -> SQLiteRepository:
        return app.extensions["macro_tracker_repository"]

    def get_fast_food_service() -> FastFoodService:
        return app.extensions["macro_tracker_fast_food_service"]

    def get_smart_food_service() -> SmartFoodService:
        return app.extensions["macro_tracker_smart_food_service"]

    def get_label_service() -> NutritionLabelService:
        return app.extensions["macro_tracker_label_service"]

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        return jsonify({"error": str(error)}), 400

    @app.context_processor
    def inject_layout_values():
        return {"current_date": current_date()}

    @app.route("/")
    def index():
        today = current_date()
        return render_template(
            "index.html",
            page_title="Dashboard",
            active_page="dashboard",
            default_date=today,
            dashboard=get_repository().get_dashboard(today),
        )

    @app.route("/assistant")
    def assistant():
        return render_template(
            "assistant.html",
            page_title="Smart Log",
            active_page="assistant",
            default_date=current_date(),
            saved_meals=get_repository().list_saved_meals(),
            library_items=get_repository().list_library_items(),
        )

    @app.route("/library")
    def library():
        return render_template(
            "library.html",
            page_title="Library",
            active_page="library",
            saved_meals=get_repository().list_saved_meals(),
            library_items=get_repository().list_library_items(),
        )

    @app.route("/fast-food")
    def fast_food():
        return render_template(
            "fast_food.html",
            page_title="Fast Food",
            active_page="fast_food",
            default_date=current_date(),
        )

    @app.route("/settings")
    def settings():
        return render_template(
            "settings.html",
            page_title="Settings",
            active_page="settings",
            settings=get_repository().get_settings(),
        )

    @app.route("/week")
    @app.route("/dining")
    def removed_pages():
        return redirect(url_for("index"))

    @app.get("/api/dashboard")
    def api_dashboard():
        date = request.args.get("date", current_date())
        return jsonify(get_repository().get_dashboard(parse_date(date)))

    @app.get("/api/day/<date>")
    def api_day(date: str):
        return jsonify(get_repository().get_day(parse_date(date)))

    @app.post("/api/day/burn")
    def api_day_burn():
        payload = request.get_json(silent=True) or {}
        burn = get_repository().upsert_daily_burn(
            entry_date=payload.get("date"),
            calories_burned=payload.get("calories_burned"),
        )
        return jsonify(
            {
                "status": "success",
                "burn": burn,
                "dashboard": get_repository().get_dashboard(burn["date"]),
            }
        )

    @app.post("/api/meals")
    def api_create_meal():
        payload = request.get_json(silent=True) or {}
        entry = get_repository().add_meal_entry(
            entry_date=payload.get("date"),
            name=payload.get("name") or payload.get("meal_name"),
            protein_g=payload.get("protein_g", payload.get("protein", 0)),
            carbs_g=payload.get("carbs_g", payload.get("carbs", 0)),
            fat_g=payload.get("fat_g", payload.get("fat", 0)),
            calories=payload.get("calories", 0),
            source=payload.get("source", "manual"),
            servings=payload.get("servings", 1),
        )
        return jsonify(
            {
                "status": "success",
                "meal": entry,
                "day": get_repository().get_day(entry["date"]),
                "dashboard": get_repository().get_dashboard(entry["date"]),
            }
        ), 201

    @app.delete("/api/meals/<int:entry_id>")
    def api_delete_meal(entry_id: int):
        deleted = get_repository().delete_meal_entry(entry_id)
        if not deleted:
            return jsonify({"error": "Meal entry not found."}), 404
        return jsonify({"status": "success"})

    @app.get("/api/settings")
    def api_get_settings():
        return jsonify(get_repository().get_settings())

    @app.post("/api/settings")
    def api_update_settings():
        payload = request.get_json(silent=True) or {}
        settings_data = get_repository().update_settings(
            payload.get("daily_calorie_goal", payload.get("calorie_goal")),
            payload.get("daily_protein_goal", payload.get("protein_goal")),
            payload.get("daily_carbs_goal", payload.get("carbs_goal")),
            payload.get("daily_fat_goal", payload.get("fat_goal")),
            payload.get("default_calories_burned", payload.get("daily_burn_goal")),
        )
        return jsonify({"status": "success", "settings": settings_data})

    @app.get("/api/saved-meals")
    def api_saved_meals():
        return jsonify({"saved_meals": get_repository().list_saved_meals()})

    @app.post("/api/saved-meals")
    def api_create_saved_meal():
        payload = request.get_json(silent=True) or {}
        saved_meal = get_repository().create_saved_meal(
            name=payload.get("name"),
            protein_g=payload.get("protein_g", payload.get("protein", 0)),
            carbs_g=payload.get("carbs_g", payload.get("carbs", 0)),
            fat_g=payload.get("fat_g", payload.get("fat", 0)),
            calories=payload.get("calories", 0),
        )
        return jsonify(
            {
                "status": "success",
                "saved_meal": saved_meal,
                "saved_meals": get_repository().list_saved_meals(),
            }
        ), 201

    @app.delete("/api/saved-meals/<int:saved_meal_id>")
    def api_delete_saved_meal(saved_meal_id: int):
        deleted = get_repository().delete_saved_meal(saved_meal_id)
        if not deleted:
            return jsonify({"error": "Saved meal not found."}), 404
        return jsonify({"status": "success", "saved_meals": get_repository().list_saved_meals()})

    @app.post("/api/saved-meals/<int:saved_meal_id>/log")
    def api_log_saved_meal(saved_meal_id: int):
        payload = request.get_json(silent=True) or {}
        meal = get_repository().log_saved_meal(
            saved_meal_id=saved_meal_id,
            entry_date=payload.get("date"),
            servings=payload.get("servings", 1),
        )
        return jsonify(
            {
                "status": "success",
                "meal": meal,
                "day": get_repository().get_day(meal["date"]),
                "dashboard": get_repository().get_dashboard(meal["date"]),
            }
        ), 201

    @app.get("/api/library-items")
    def api_library_items():
        return jsonify({"library_items": get_repository().list_library_items()})

    @app.post("/api/library-items")
    def api_create_library_item():
        payload = request.get_json(silent=True) or {}
        item = get_repository().create_library_item(
            name=payload.get("name"),
            brand=payload.get("brand", ""),
            serving_amount=payload.get("serving_amount", 1),
            serving_unit=payload.get("serving_unit", "serving"),
            calories=payload.get("calories", 0),
            protein_g=payload.get("protein_g", 0),
            carbs_g=payload.get("carbs_g", 0),
            fat_g=payload.get("fat_g", 0),
            source=payload.get("source", "manual"),
            notes=payload.get("notes", ""),
            image_path=payload.get("image_path", ""),
            extracted_text=payload.get("extracted_text", ""),
        )
        return jsonify({"status": "success", "library_item": item, "library_items": get_repository().list_library_items()}), 201

    @app.delete("/api/library-items/<int:item_id>")
    def api_delete_library_item(item_id: int):
        deleted = get_repository().delete_library_item(item_id)
        if not deleted:
            return jsonify({"error": "Library item not found."}), 404
        return jsonify({"status": "success", "library_items": get_repository().list_library_items()})

    @app.post("/api/library-items/<int:item_id>/log")
    def api_log_library_item(item_id: int):
        payload = request.get_json(silent=True) or {}
        meal = get_repository().log_library_item(
            item_id=item_id,
            entry_date=payload.get("date"),
            servings=payload.get("servings", 1),
        )
        return jsonify(
            {
                "status": "success",
                "meal": meal,
                "day": get_repository().get_day(meal["date"]),
                "dashboard": get_repository().get_dashboard(meal["date"]),
            }
        ), 201

    @app.post("/api/assistant/estimate")
    def api_assistant_estimate():
        payload = request.get_json(silent=True) or {}
        estimate = get_smart_food_service().estimate_from_text(
            query=payload.get("query"),
            known_calories=payload.get("known_calories"),
        )
        return jsonify({"status": "success", "estimate": estimate})

    @app.post("/api/assistant/scan-label")
    def api_scan_label():
        image = request.files.get("image")
        if image is None or not image.filename:
            return jsonify({"error": "A nutrition label image is required."}), 400

        parsed = get_label_service().parse_uploaded_label(
            image_bytes=image.read(),
            filename=image.filename,
            fallback_name=request.form.get("name"),
            fallback_brand=request.form.get("brand"),
        )
        return jsonify({"status": "success", "estimate": parsed})

    @app.get("/api/fast-food")
    def api_fast_food():
        return jsonify(get_fast_food_service().get_catalog())

    @app.post("/api/fast-food/log")
    def api_fast_food_log():
        payload = request.get_json(silent=True) or {}
        meal = get_fast_food_service().log_item(
            item_id=payload.get("item_id"),
            date=payload.get("date"),
            servings=payload.get("servings", 1),
        )
        return jsonify(
            {
                "status": "success",
                "meal": meal,
                "day": get_repository().get_day(meal["date"]),
                "dashboard": get_repository().get_dashboard(meal["date"]),
            }
        ), 201

    return app


def current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1").lower() not in {"0", "false", "no", "off"}
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=debug, host=host, port=port)
