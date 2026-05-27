from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_SETTINGS = {
    "daily_calorie_goal": 2200.0,
    "daily_protein_goal": 150.0,
    "daily_carbs_goal": 200.0,
    "daily_fat_goal": 65.0,
    "default_calories_burned": 2600.0,
}


class ValidationError(ValueError):
    """Raised when a request payload is invalid."""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise ValidationError("Dates must use YYYY-MM-DD format.") from exc


def coerce_float(value: Any, *, field_name: str, minimum: float = 0.0) -> float:
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a number.") from exc

    if numeric < minimum:
        raise ValidationError(f"{field_name} must be at least {minimum}.")

    return round(numeric, 2)


class SQLiteRepository:
    def __init__(self, db_path: str | Path = "macro_tracker.db", legacy_json_path: str | Path = "macros.json"):
        self.db_path = Path(db_path)
        self.legacy_json_path = Path(legacy_json_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    daily_protein_goal REAL NOT NULL,
                    daily_carbs_goal REAL NOT NULL,
                    daily_fat_goal REAL NOT NULL,
                    legacy_imported_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS meal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_date TEXT NOT NULL,
                    name TEXT NOT NULL,
                    protein_g REAL NOT NULL,
                    carbs_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    calories REAL NOT NULL,
                    source TEXT NOT NULL,
                    servings REAL NOT NULL DEFAULT 1.0,
                    menu_item_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS saved_meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    protein_g REAL NOT NULL,
                    carbs_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    calories REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS menu_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,
                    menu_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    warning TEXT,
                    source TEXT NOT NULL,
                    error_message TEXT,
                    UNIQUE(location, menu_date)
                );

                CREATE TABLE IF NOT EXISTS menu_items (
                    id TEXT PRIMARY KEY,
                    snapshot_id INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    menu_date TEXT NOT NULL,
                    period TEXT NOT NULL,
                    station TEXT NOT NULL,
                    name TEXT NOT NULL,
                    serving_label TEXT,
                    calories REAL NOT NULL,
                    protein_g REAL NOT NULL,
                    carbs_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    ingredients TEXT NOT NULL,
                    allergens TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    FOREIGN KEY(snapshot_id) REFERENCES menu_snapshots(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,
                    menu_date TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    snapshot_id INTEGER,
                    FOREIGN KEY(snapshot_id) REFERENCES menu_snapshots(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS daily_burn_logs (
                    entry_date TEXT PRIMARY KEY,
                    calories_burned REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS library_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    brand TEXT,
                    serving_amount REAL NOT NULL,
                    serving_unit TEXT NOT NULL,
                    calories REAL NOT NULL,
                    protein_g REAL NOT NULL,
                    carbs_g REAL NOT NULL,
                    fat_g REAL NOT NULL,
                    source TEXT NOT NULL,
                    notes TEXT,
                    image_path TEXT,
                    extracted_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            self._ensure_settings_column(
                conn,
                column_name="daily_calorie_goal",
                column_type="REAL NOT NULL DEFAULT 2200",
            )
            self._ensure_settings_column(
                conn,
                column_name="default_calories_burned",
                column_type="REAL NOT NULL DEFAULT 2600",
            )

            duplicate_running_rows = conn.execute(
                """
                SELECT id, location, menu_date
                FROM sync_runs
                WHERE status = 'running'
                ORDER BY location ASC, menu_date ASC, started_at ASC, id ASC
                """
            ).fetchall()
            seen_active_keys: set[tuple[str, str]] = set()
            for row in duplicate_running_rows:
                key = (str(row["location"]), str(row["menu_date"]))
                if key in seen_active_keys:
                    conn.execute(
                        """
                        UPDATE sync_runs
                        SET finished_at = ?,
                            status = 'failed',
                            error_message = ?
                        WHERE id = ?
                        """,
                        (now_iso(), "Superseded by another in-progress sync.", row["id"]),
                    )
                    continue
                seen_active_keys.add(key)

            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_runs_active
                ON sync_runs(location, menu_date)
                WHERE status = 'running'
                """
            )

            existing = conn.execute("SELECT id FROM settings WHERE id = 1").fetchone()
            if existing is None:
                timestamp = now_iso()
                conn.execute(
                    """
                    INSERT INTO settings (
                        id,
                        daily_calorie_goal,
                        daily_protein_goal,
                        daily_carbs_goal,
                        daily_fat_goal,
                        default_calories_burned,
                        legacy_imported_at,
                        created_at,
                        updated_at
                    ) VALUES (1, ?, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        DEFAULT_SETTINGS["daily_calorie_goal"],
                        DEFAULT_SETTINGS["daily_protein_goal"],
                        DEFAULT_SETTINGS["daily_carbs_goal"],
                        DEFAULT_SETTINGS["daily_fat_goal"],
                        DEFAULT_SETTINGS["default_calories_burned"],
                        timestamp,
                        timestamp,
                    ),
                )

        self.import_legacy_json_if_needed()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _setting_row(self, conn: sqlite3.Connection) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        if row is None:
            raise RuntimeError("Settings row is missing.")
        return row

    def _ensure_settings_column(self, conn: sqlite3.Connection, *, column_name: str, column_type: str) -> None:
        existing_columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
        if column_name in existing_columns:
            return
        conn.execute(f"ALTER TABLE settings ADD COLUMN {column_name} {column_type}")

    def import_legacy_json_if_needed(self) -> None:
        if not self.legacy_json_path.exists():
            return

        raw = self.legacy_json_path.read_text()
        if not raw.strip():
            return

        try:
            legacy = json.loads(raw)
        except json.JSONDecodeError:
            return

        with self.transaction() as conn:
            settings_row = self._setting_row(conn)
            if settings_row["legacy_imported_at"]:
                return

            legacy_settings = legacy.get("settings") or {}
            conn.execute(
                """
                UPDATE settings
                SET daily_calorie_goal = ?,
                    daily_protein_goal = ?,
                    daily_carbs_goal = ?,
                    daily_fat_goal = ?,
                    default_calories_burned = ?,
                    legacy_imported_at = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    coerce_float(
                        legacy_settings.get("daily_calorie_goal", DEFAULT_SETTINGS["daily_calorie_goal"]),
                        field_name="daily_calorie_goal",
                    ),
                    coerce_float(
                        legacy_settings.get("daily_protein_goal", DEFAULT_SETTINGS["daily_protein_goal"]),
                        field_name="daily_protein_goal",
                    ),
                    coerce_float(
                        legacy_settings.get("daily_carbs_goal", DEFAULT_SETTINGS["daily_carbs_goal"]),
                        field_name="daily_carbs_goal",
                    ),
                    coerce_float(
                        legacy_settings.get("daily_fat_goal", DEFAULT_SETTINGS["daily_fat_goal"]),
                        field_name="daily_fat_goal",
                    ),
                    coerce_float(
                        legacy_settings.get("default_calories_burned", DEFAULT_SETTINGS["default_calories_burned"]),
                        field_name="default_calories_burned",
                    ),
                    now_iso(),
                    now_iso(),
                ),
            )

            macros = legacy.get("macros") or {}
            for date_key, meals in macros.items():
                normalized_date = parse_date(date_key)
                for meal in meals:
                    conn.execute(
                        """
                        INSERT INTO meal_entries (
                            entry_date,
                            name,
                            protein_g,
                            carbs_g,
                            fat_g,
                            calories,
                            source,
                            servings,
                            menu_item_id,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            normalized_date,
                            str(meal.get("meal", "Imported meal")).strip() or "Imported meal",
                            coerce_float(meal.get("protein", 0), field_name="protein_g"),
                            coerce_float(meal.get("carbs", 0), field_name="carbs_g"),
                            coerce_float(meal.get("fat", 0), field_name="fat_g"),
                            coerce_float(meal.get("calories", 0), field_name="calories"),
                            "manual",
                            1.0,
                            None,
                            meal.get("timestamp") or now_iso(),
                        ),
                    )

    def get_settings(self) -> dict[str, float]:
        with self.transaction() as conn:
            row = self._setting_row(conn)
            return {
                "daily_calorie_goal": row["daily_calorie_goal"],
                "daily_protein_goal": row["daily_protein_goal"],
                "daily_carbs_goal": row["daily_carbs_goal"],
                "daily_fat_goal": row["daily_fat_goal"],
                "default_calories_burned": row["default_calories_burned"],
            }

    def update_settings(
        self,
        calorie_goal: Any,
        protein_goal: Any,
        carbs_goal: Any,
        fat_goal: Any,
        default_calories_burned: Any,
    ) -> dict[str, float]:
        calories = coerce_float(calorie_goal, field_name="daily_calorie_goal")
        protein = coerce_float(protein_goal, field_name="daily_protein_goal")
        carbs = coerce_float(carbs_goal, field_name="daily_carbs_goal")
        fat = coerce_float(fat_goal, field_name="daily_fat_goal")
        burn = coerce_float(default_calories_burned, field_name="default_calories_burned")

        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE settings
                SET daily_calorie_goal = ?,
                    daily_protein_goal = ?,
                    daily_carbs_goal = ?,
                    daily_fat_goal = ?,
                    default_calories_burned = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (calories, protein, carbs, fat, burn, now_iso()),
            )

        return self.get_settings()

    def add_meal_entry(
        self,
        *,
        entry_date: Any,
        name: Any,
        protein_g: Any,
        carbs_g: Any,
        fat_g: Any,
        calories: Any,
        source: str,
        servings: Any = 1.0,
        menu_item_id: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        normalized_date = parse_date(str(entry_date))
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValidationError("name is required.")

        normalized_source = str(source).strip() or "manual"
        allowed_sources = {
            "manual",
            "saved_meal",
            "fast_food",
            "assistant_text",
            "label_scan",
            "library_item",
        }
        if normalized_source not in allowed_sources:
            raise ValidationError(f"source must be one of: {', '.join(sorted(allowed_sources))}.")

        normalized_servings = coerce_float(servings, field_name="servings", minimum=0.01)

        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO meal_entries (
                    entry_date,
                    name,
                    protein_g,
                    carbs_g,
                    fat_g,
                    calories,
                    source,
                    servings,
                    menu_item_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_date,
                    normalized_name,
                    coerce_float(protein_g, field_name="protein_g"),
                    coerce_float(carbs_g, field_name="carbs_g"),
                    coerce_float(fat_g, field_name="fat_g"),
                    coerce_float(calories, field_name="calories"),
                    normalized_source,
                    normalized_servings,
                    menu_item_id,
                    created_at or now_iso(),
                ),
            )
            row = conn.execute(
                "SELECT * FROM meal_entries WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()

        if row is None:
            raise RuntimeError("Meal entry insert failed.")

        return self._row_to_meal_entry(row)

    def delete_meal_entry(self, entry_id: int) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM meal_entries WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0

    def create_saved_meal(
        self,
        *,
        name: Any,
        protein_g: Any,
        carbs_g: Any,
        fat_g: Any,
        calories: Any,
    ) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValidationError("name is required.")

        timestamp = now_iso()
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO saved_meals (
                    name,
                    protein_g,
                    carbs_g,
                    fat_g,
                    calories,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_name,
                    coerce_float(protein_g, field_name="protein_g"),
                    coerce_float(carbs_g, field_name="carbs_g"),
                    coerce_float(fat_g, field_name="fat_g"),
                    coerce_float(calories, field_name="calories"),
                    timestamp,
                    timestamp,
                ),
            )
            row = conn.execute("SELECT * FROM saved_meals WHERE id = ?", (cursor.lastrowid,)).fetchone()

        if row is None:
            raise RuntimeError("Saved meal insert failed.")

        return self._row_to_saved_meal(row)

    def list_saved_meals(self) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM saved_meals
                ORDER BY lower(name) ASC, id DESC
                """
            ).fetchall()
        return [self._row_to_saved_meal(row) for row in rows]

    def get_saved_meal(self, saved_meal_id: int) -> dict[str, Any] | None:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM saved_meals WHERE id = ?", (saved_meal_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_saved_meal(row)

    def update_saved_meal(
        self,
        saved_meal_id: int,
        *,
        name: Any,
        protein_g: Any,
        carbs_g: Any,
        fat_g: Any,
        calories: Any,
    ) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValidationError("name is required.")

        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE saved_meals
                SET name = ?,
                    protein_g = ?,
                    carbs_g = ?,
                    fat_g = ?,
                    calories = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_name,
                    coerce_float(protein_g, field_name="protein_g"),
                    coerce_float(carbs_g, field_name="carbs_g"),
                    coerce_float(fat_g, field_name="fat_g"),
                    coerce_float(calories, field_name="calories"),
                    now_iso(),
                    saved_meal_id,
                ),
            )
            if cursor.rowcount <= 0:
                raise ValidationError("Saved meal not found.")
            row = conn.execute("SELECT * FROM saved_meals WHERE id = ?", (saved_meal_id,)).fetchone()

        if row is None:
            raise RuntimeError("Saved meal update failed.")
        return self._row_to_saved_meal(row)

    def delete_saved_meal(self, saved_meal_id: int) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM saved_meals WHERE id = ?", (saved_meal_id,))
            return cursor.rowcount > 0

    def log_saved_meal(self, *, saved_meal_id: int, entry_date: Any, servings: Any = 1.0) -> dict[str, Any]:
        saved_meal = self.get_saved_meal(saved_meal_id)
        if saved_meal is None:
            raise ValidationError("Saved meal not found.")

        normalized_servings = coerce_float(servings, field_name="servings", minimum=0.01)
        return self.add_meal_entry(
            entry_date=entry_date,
            name=saved_meal["name"],
            protein_g=round(saved_meal["protein_g"] * normalized_servings, 2),
            carbs_g=round(saved_meal["carbs_g"] * normalized_servings, 2),
            fat_g=round(saved_meal["fat_g"] * normalized_servings, 2),
            calories=round(saved_meal["calories"] * normalized_servings, 2),
            source="saved_meal",
            servings=normalized_servings,
        )

    def upsert_daily_burn(self, *, entry_date: Any, calories_burned: Any) -> dict[str, Any]:
        normalized_date = parse_date(str(entry_date))
        normalized_burn = coerce_float(calories_burned, field_name="calories_burned")
        timestamp = now_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO daily_burn_logs (entry_date, calories_burned, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(entry_date) DO UPDATE SET
                    calories_burned = excluded.calories_burned,
                    updated_at = excluded.updated_at
                """,
                (normalized_date, normalized_burn, timestamp),
            )
        return {
            "date": normalized_date,
            "calories_burned": normalized_burn,
            "updated_at": timestamp,
        }

    def get_daily_burn(self, entry_date: str) -> float:
        normalized_date = parse_date(entry_date)
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT calories_burned FROM daily_burn_logs WHERE entry_date = ?",
                (normalized_date,),
            ).fetchone()
            if row is not None:
                return round(float(row["calories_burned"]), 2)
            settings_row = self._setting_row(conn)
            return round(float(settings_row["default_calories_burned"]), 2)

    def create_library_item(
        self,
        *,
        name: Any,
        brand: Any = "",
        serving_amount: Any = 1.0,
        serving_unit: Any = "serving",
        calories: Any,
        protein_g: Any,
        carbs_g: Any,
        fat_g: Any,
        source: Any = "manual",
        notes: Any = "",
        image_path: Any = "",
        extracted_text: Any = "",
    ) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValidationError("name is required.")

        normalized_serving_amount = coerce_float(serving_amount, field_name="serving_amount", minimum=0.01)
        normalized_serving_unit = str(serving_unit or "serving").strip() or "serving"
        normalized_source = str(source or "manual").strip() or "manual"
        timestamp = now_iso()

        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO library_items (
                    name,
                    brand,
                    serving_amount,
                    serving_unit,
                    calories,
                    protein_g,
                    carbs_g,
                    fat_g,
                    source,
                    notes,
                    image_path,
                    extracted_text,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_name,
                    str(brand or "").strip(),
                    normalized_serving_amount,
                    normalized_serving_unit,
                    coerce_float(calories, field_name="calories"),
                    coerce_float(protein_g, field_name="protein_g"),
                    coerce_float(carbs_g, field_name="carbs_g"),
                    coerce_float(fat_g, field_name="fat_g"),
                    normalized_source,
                    str(notes or "").strip(),
                    str(image_path or "").strip(),
                    str(extracted_text or "").strip(),
                    timestamp,
                    timestamp,
                ),
            )
            row = conn.execute("SELECT * FROM library_items WHERE id = ?", (cursor.lastrowid,)).fetchone()

        if row is None:
            raise RuntimeError("Library item insert failed.")
        return self._row_to_library_item(row)

    def list_library_items(self) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM library_items
                ORDER BY updated_at DESC, lower(name) ASC
                """
            ).fetchall()
        return [self._row_to_library_item(row) for row in rows]

    def get_library_item(self, item_id: int) -> dict[str, Any] | None:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM library_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_library_item(row)

    def update_library_item(
        self,
        item_id: int,
        *,
        name: Any,
        brand: Any = "",
        serving_amount: Any = 1.0,
        serving_unit: Any = "serving",
        calories: Any,
        protein_g: Any,
        carbs_g: Any,
        fat_g: Any,
        notes: Any = "",
        source: Any | None = None,
    ) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValidationError("name is required.")

        existing_item = self.get_library_item(item_id)
        if existing_item is None:
            raise ValidationError("Library item not found.")

        normalized_source = str(source or existing_item["source"]).strip() or existing_item["source"]

        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE library_items
                SET name = ?,
                    brand = ?,
                    serving_amount = ?,
                    serving_unit = ?,
                    calories = ?,
                    protein_g = ?,
                    carbs_g = ?,
                    fat_g = ?,
                    source = ?,
                    notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_name,
                    str(brand or "").strip(),
                    coerce_float(serving_amount, field_name="serving_amount", minimum=0.01),
                    str(serving_unit or "serving").strip() or "serving",
                    coerce_float(calories, field_name="calories"),
                    coerce_float(protein_g, field_name="protein_g"),
                    coerce_float(carbs_g, field_name="carbs_g"),
                    coerce_float(fat_g, field_name="fat_g"),
                    normalized_source,
                    str(notes or "").strip(),
                    now_iso(),
                    item_id,
                ),
            )
            if cursor.rowcount <= 0:
                raise ValidationError("Library item not found.")
            row = conn.execute("SELECT * FROM library_items WHERE id = ?", (item_id,)).fetchone()

        if row is None:
            raise RuntimeError("Library item update failed.")
        return self._row_to_library_item(row)

    def delete_library_item(self, item_id: int) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM library_items WHERE id = ?", (item_id,))
            return cursor.rowcount > 0

    def log_library_item(self, *, item_id: int, entry_date: Any, servings: Any = 1.0) -> dict[str, Any]:
        item = self.get_library_item(item_id)
        if item is None:
            raise ValidationError("Library item not found.")

        normalized_servings = coerce_float(servings, field_name="servings", minimum=0.01)
        return self.add_meal_entry(
            entry_date=entry_date,
            name=f'{item["brand"] + " - " if item["brand"] else ""}{item["name"]}',
            protein_g=round(item["protein_g"] * normalized_servings, 2),
            carbs_g=round(item["carbs_g"] * normalized_servings, 2),
            fat_g=round(item["fat_g"] * normalized_servings, 2),
            calories=round(item["calories"] * normalized_servings, 2),
            source="library_item",
            servings=normalized_servings,
            menu_item_id=str(item["id"]),
        )

    def get_day(self, date: str) -> dict[str, Any]:
        normalized_date = parse_date(date)
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM meal_entries
                WHERE entry_date = ?
                ORDER BY created_at DESC, id DESC
                """,
                (normalized_date,),
            ).fetchall()
            burn_row = conn.execute(
                "SELECT calories_burned FROM daily_burn_logs WHERE entry_date = ?",
                (normalized_date,),
            ).fetchone()
            settings_row = self._setting_row(conn)

        meals = [self._row_to_meal_entry(row) for row in rows]
        calories_burned = (
            round(float(burn_row["calories_burned"]), 2)
            if burn_row is not None
            else round(float(settings_row["default_calories_burned"]), 2)
        )
        totals = {
            "protein_g": round(sum(meal["protein_g"] for meal in meals), 2),
            "carbs_g": round(sum(meal["carbs_g"] for meal in meals), 2),
            "fat_g": round(sum(meal["fat_g"] for meal in meals), 2),
            "calories": round(sum(meal["calories"] for meal in meals), 2),
        }
        return {
            "date": normalized_date,
            "totals": totals,
            "meals": meals,
            "calories_burned": calories_burned,
            "deficit": round(calories_burned - totals["calories"], 2),
            "remaining_calories": round(float(settings_row["daily_calorie_goal"]) - totals["calories"], 2),
        }

    def get_week_summaries(self, *, end_date: str, days: int = 7) -> list[dict[str, Any]]:
        normalized_end = datetime.strptime(parse_date(end_date), "%Y-%m-%d")
        summaries = []
        for offset in range(days):
            date_value = (normalized_end - timedelta(days=offset)).strftime("%Y-%m-%d")
            day = self.get_day(date_value)
            summaries.append(
                {
                    "date": date_value,
                    **day["totals"],
                    "calories_burned": day["calories_burned"],
                    "deficit": day["deficit"],
                }
            )
        return summaries

    def get_weekly_deficit_archive(self, *, end_date: str, weeks: int = 8) -> list[dict[str, Any]]:
        normalized_end = datetime.strptime(parse_date(end_date), "%Y-%m-%d")
        end_of_week = normalized_end - timedelta(days=normalized_end.weekday())
        archive = []
        for week_offset in range(weeks):
            start = end_of_week - timedelta(days=7 * week_offset)
            dates = [(start + timedelta(days=day)).strftime("%Y-%m-%d") for day in range(7)]
            entries = [self.get_day(date_value) for date_value in dates]
            archive.append(
                {
                    "week_start": dates[0],
                    "week_end": dates[-1],
                    "weekly_deficit": round(sum(entry["deficit"] for entry in entries), 2),
                    "calories_consumed": round(sum(entry["totals"]["calories"] for entry in entries), 2),
                    "calories_burned": round(sum(entry["calories_burned"] for entry in entries), 2),
                }
            )
        return archive

    def get_dashboard(self, date: str) -> dict[str, Any]:
        normalized_date = parse_date(date)
        day = self.get_day(normalized_date)
        settings = self.get_settings()
        weekly = list(reversed(self.get_week_summaries(end_date=normalized_date, days=7)))
        deficit_archive = self.get_weekly_deficit_archive(end_date=normalized_date, weeks=8)

        calorie_progress = (
            min(1.25, day["totals"]["calories"] / settings["daily_calorie_goal"])
            if settings["daily_calorie_goal"]
            else 0.0
        )
        macro_progress = {
            "protein": min(1.25, day["totals"]["protein_g"] / settings["daily_protein_goal"])
            if settings["daily_protein_goal"]
            else 0.0,
            "carbs": min(1.25, day["totals"]["carbs_g"] / settings["daily_carbs_goal"])
            if settings["daily_carbs_goal"]
            else 0.0,
            "fat": min(1.25, day["totals"]["fat_g"] / settings["daily_fat_goal"])
            if settings["daily_fat_goal"]
            else 0.0,
        }

        return {
            "date": normalized_date,
            "settings": settings,
            "day": day,
            "calorie_progress": round(calorie_progress, 3),
            "macro_progress": macro_progress,
            "weekly": weekly,
            "weekly_deficit_total": round(sum(day_item["deficit"] for day_item in weekly), 2),
            "weekly_calories_total": round(sum(day_item["calories"] for day_item in weekly), 2),
            "weekly_burn_total": round(sum(day_item["calories_burned"] for day_item in weekly), 2),
            "deficit_archive": deficit_archive,
        }

    def record_sync_run_started(self, *, location: str, menu_date: str) -> int:
        with self.transaction() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO sync_runs (location, menu_date, started_at, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (location, parse_date(menu_date), now_iso(), "running"),
                )
            except sqlite3.IntegrityError:
                return 0
            return int(cursor.lastrowid)

    def record_sync_run_finished(
        self,
        *,
        run_id: int,
        status: str,
        error_message: str | None = None,
        snapshot_id: int | None = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?,
                    status = ?,
                    error_message = ?,
                    snapshot_id = ?
                WHERE id = ?
                """,
                (now_iso(), status, error_message, snapshot_id, run_id),
            )

    def get_active_sync_run(
        self,
        *,
        location: str,
        menu_date: str,
        stale_after_minutes: int = 10,
    ) -> dict[str, Any] | None:
        normalized_date = parse_date(menu_date)
        cutoff = datetime.now(timezone.utc).astimezone() - timedelta(minutes=stale_after_minutes)
        cutoff_iso = cutoff.isoformat(timespec="seconds")
        finished_at = now_iso()

        with self.transaction() as conn:
            running_rows = conn.execute(
                """
                SELECT *
                FROM sync_runs
                WHERE location = ? AND menu_date = ? AND status = 'running'
                ORDER BY started_at ASC, id ASC
                """,
                (location, normalized_date),
            ).fetchall()

            active_row = None
            for index, row in enumerate(running_rows):
                row_started_at = str(row["started_at"] or "")
                is_stale = row_started_at < cutoff_iso
                is_duplicate = index > 0
                if is_stale or is_duplicate:
                    reason = "Sync timed out before finishing." if is_stale else "Superseded by another in-progress sync."
                    conn.execute(
                        """
                        UPDATE sync_runs
                        SET finished_at = ?,
                            status = 'failed',
                            error_message = ?
                        WHERE id = ?
                        """,
                        (finished_at, reason, row["id"]),
                    )
                    continue

                active_row = row

            if active_row is None:
                return None

            return {
                "id": active_row["id"],
                "location": active_row["location"],
                "menu_date": active_row["menu_date"],
                "started_at": active_row["started_at"],
                "finished_at": active_row["finished_at"],
                "status": active_row["status"],
                "error_message": active_row["error_message"],
                "snapshot_id": active_row["snapshot_id"],
            }

    def save_menu_snapshot(self, menu_payload: dict[str, Any]) -> int:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO menu_snapshots (
                    location,
                    menu_date,
                    status,
                    fetched_at,
                    warning,
                    source,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(location, menu_date) DO UPDATE SET
                    status = excluded.status,
                    fetched_at = excluded.fetched_at,
                    warning = excluded.warning,
                    source = excluded.source,
                    error_message = excluded.error_message
                """,
                (
                    menu_payload["location"],
                    parse_date(menu_payload["date"]),
                    menu_payload["status"],
                    menu_payload["fetched_at"],
                    menu_payload.get("warning"),
                    menu_payload.get("source", "playwright"),
                    menu_payload.get("error"),
                ),
            )
            snapshot = conn.execute(
                """
                SELECT id
                FROM menu_snapshots
                WHERE location = ? AND menu_date = ?
                """,
                (menu_payload["location"], parse_date(menu_payload["date"])),
            ).fetchone()
            if snapshot is None:
                raise RuntimeError("Unable to locate saved snapshot.")

            snapshot_id = int(snapshot["id"])
            conn.execute("DELETE FROM menu_items WHERE snapshot_id = ?", (snapshot_id,))

            for item in self._iter_snapshot_items(menu_payload):
                conn.execute(
                    """
                    INSERT INTO menu_items (
                        id,
                        snapshot_id,
                        location,
                        menu_date,
                        period,
                        station,
                        name,
                        serving_label,
                        calories,
                        protein_g,
                        carbs_g,
                        fat_g,
                        ingredients,
                        allergens,
                        source_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"],
                        snapshot_id,
                        item["location"],
                        item["date"],
                        item["period"],
                        item["station"],
                        item["name"],
                        item.get("serving_label", ""),
                        item["calories"],
                        item["protein_g"],
                        item["carbs_g"],
                        item["fat_g"],
                        json.dumps(item.get("ingredients", [])),
                        json.dumps(item.get("allergens", [])),
                        item["source_hash"],
                    ),
                )

            return snapshot_id

    def get_menu_snapshot(self, *, location: str, menu_date: str) -> dict[str, Any] | None:
        normalized_date = parse_date(menu_date)
        with self.transaction() as conn:
            snapshot = conn.execute(
                """
                SELECT *
                FROM menu_snapshots
                WHERE location = ? AND menu_date = ?
                """,
                (location, normalized_date),
            ).fetchone()
            if snapshot is None:
                return None

            items = conn.execute(
                """
                SELECT *
                FROM menu_items
                WHERE snapshot_id = ?
                ORDER BY period ASC, station ASC, name ASC
                """,
                (snapshot["id"],),
            ).fetchall()

        periods: dict[str, list[dict[str, Any]]] = {}
        for item_row in items:
            item = self._row_to_menu_item(item_row)
            periods.setdefault(item["period"], []).append(item)

        return {
            "location": snapshot["location"],
            "date": snapshot["menu_date"],
            "status": snapshot["status"],
            "fetched_at": snapshot["fetched_at"],
            "warning": snapshot["warning"],
            "periods": periods,
            "source": snapshot["source"],
        }

    def get_menu_item(self, item_id: str) -> dict[str, Any] | None:
        with self.transaction() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM menu_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_menu_item(row)

    def _iter_snapshot_items(self, menu_payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
        for period_name, items in (menu_payload.get("periods") or {}).items():
            for item in items:
                yield {**item, "period": period_name}

    def _row_to_meal_entry(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "date": row["entry_date"],
            "name": row["name"],
            "protein_g": row["protein_g"],
            "carbs_g": row["carbs_g"],
            "fat_g": row["fat_g"],
            "calories": row["calories"],
            "source": row["source"],
            "servings": row["servings"],
            "menu_item_id": row["menu_item_id"],
            "created_at": row["created_at"],
        }

    def _row_to_menu_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "location": row["location"],
            "date": row["menu_date"],
            "period": row["period"],
            "station": row["station"],
            "name": row["name"],
            "serving_label": row["serving_label"] or "",
            "calories": row["calories"],
            "protein_g": row["protein_g"],
            "carbs_g": row["carbs_g"],
            "fat_g": row["fat_g"],
            "ingredients": json.loads(row["ingredients"] or "[]"),
            "allergens": json.loads(row["allergens"] or "[]"),
            "source_hash": row["source_hash"],
        }

    def _row_to_saved_meal(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "protein_g": row["protein_g"],
            "carbs_g": row["carbs_g"],
            "fat_g": row["fat_g"],
            "calories": row["calories"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_library_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "brand": row["brand"] or "",
            "serving_amount": row["serving_amount"],
            "serving_unit": row["serving_unit"],
            "calories": row["calories"],
            "protein_g": row["protein_g"],
            "carbs_g": row["carbs_g"],
            "fat_g": row["fat_g"],
            "source": row["source"],
            "notes": row["notes"] or "",
            "image_path": row["image_path"] or "",
            "extracted_text": row["extracted_text"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
