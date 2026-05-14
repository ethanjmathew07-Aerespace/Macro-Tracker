from __future__ import annotations

from typing import Any

from dining_config import DEFAULT_LOCATION_NAME, DINING_LOCATIONS
from menu_provider import MenuDocument, MenuProvider, MenuSyncError
from storage import SQLiteRepository, ValidationError, coerce_float, parse_date


class MenuSyncService:
    def __init__(
        self,
        repository: SQLiteRepository,
        provider: MenuProvider,
        *,
        default_location_name: str = DEFAULT_LOCATION_NAME,
    ):
        self.repository = repository
        self.provider = provider
        self.default_location_name = default_location_name

    def get_menu(self, *, date: str, location_name: str | None = None, refresh: bool = True) -> dict[str, Any]:
        normalized_date = parse_date(date)
        selected_location = location_name or self.default_location_name
        location = DINING_LOCATIONS[selected_location]
        cached = self.repository.get_menu_snapshot(location=selected_location, menu_date=normalized_date)

        if not refresh:
            if cached:
                return cached
            return self._error_payload(
                location=selected_location,
                date=normalized_date,
                message="No cached menu snapshot is available yet.",
            )

        active_run = self.repository.get_active_sync_run(location=selected_location, menu_date=normalized_date)
        if active_run:
            if cached:
                cached["status"] = "stale"
                cached["warning"] = "Showing the last saved menu while a live sync is already running."
                return cached
            return self._refreshing_payload(
                location=selected_location,
                date=normalized_date,
                message="A live sync is already running for this date. Check back in a moment.",
            )

        run_id = self.repository.record_sync_run_started(location=selected_location, menu_date=normalized_date)
        if not run_id:
            active_run = self.repository.get_active_sync_run(location=selected_location, menu_date=normalized_date)
            if cached:
                cached["status"] = "stale"
                cached["warning"] = "Showing the last saved menu while a live sync is already running."
                return cached
            return self._refreshing_payload(
                location=selected_location,
                date=normalized_date,
                message="A live sync is already running for this date. Check back in a moment.",
            )
        try:
            document = self.provider.fetch_menu(location, normalized_date)
            payload = document.to_dict()
            snapshot_id = self.repository.save_menu_snapshot(payload)
            self.repository.record_sync_run_finished(run_id=run_id, status="success", snapshot_id=snapshot_id)
            return payload
        except MenuSyncError as exc:
            self.repository.record_sync_run_finished(run_id=run_id, status="failed", error_message=str(exc))
            if cached:
                cached["status"] = "stale"
                cached["warning"] = f"Showing cached menu because the live sync failed: {exc}"
                return cached
            return self._error_payload(location=selected_location, date=normalized_date, message=str(exc))

    def log_menu_item(
        self,
        *,
        date: str,
        servings: Any,
        item_id: str | None = None,
        item_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_date = parse_date(date)
        normalized_servings = coerce_float(servings, field_name="servings", minimum=0.01)

        if item_id:
            base_item = self.repository.get_menu_item(item_id)
            if base_item is None:
                raise ValidationError("The requested menu item was not found in the cache.")
        elif item_payload:
            base_item = self._normalize_direct_item_payload(item_payload, normalized_date)
        else:
            raise ValidationError("Either item_id or item_payload is required.")

        return self.repository.add_meal_entry(
            entry_date=normalized_date,
            name=base_item["name"],
            protein_g=round(base_item["protein_g"] * normalized_servings, 2),
            carbs_g=round(base_item["carbs_g"] * normalized_servings, 2),
            fat_g=round(base_item["fat_g"] * normalized_servings, 2),
            calories=round(base_item["calories"] * normalized_servings, 2),
            source="dining_sync",
            servings=normalized_servings,
            menu_item_id=base_item.get("id"),
        )

    def _normalize_direct_item_payload(self, item_payload: dict[str, Any], date: str) -> dict[str, Any]:
        name = str(item_payload.get("name", "")).strip()
        if not name:
            raise ValidationError("item_payload.name is required.")

        return {
            "id": item_payload.get("id"),
            "date": date,
            "name": name,
            "protein_g": coerce_float(item_payload.get("protein_g", 0), field_name="protein_g"),
            "carbs_g": coerce_float(item_payload.get("carbs_g", 0), field_name="carbs_g"),
            "fat_g": coerce_float(item_payload.get("fat_g", 0), field_name="fat_g"),
            "calories": coerce_float(item_payload.get("calories", 0), field_name="calories"),
        }

    def _error_payload(self, *, location: str, date: str, message: str) -> dict[str, Any]:
        return {
            "location": location,
            "date": date,
            "status": "error",
            "fetched_at": None,
            "warning": None,
            "error": message,
            "periods": {},
            "source": "playwright",
        }

    def _refreshing_payload(self, *, location: str, date: str, message: str) -> dict[str, Any]:
        return {
            "location": location,
            "date": date,
            "status": "refreshing",
            "fetched_at": None,
            "warning": message,
            "error": None,
            "periods": {},
            "source": "playwright",
        }
