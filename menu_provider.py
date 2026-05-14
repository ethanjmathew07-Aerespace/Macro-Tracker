from __future__ import annotations

import hashlib
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from dining_config import DiningLocationConfig
from storage import now_iso


class MenuSyncError(RuntimeError):
    """Raised when menu sync cannot complete."""


class MenuProviderDependencyError(MenuSyncError):
    """Raised when an optional provider dependency is missing."""


@dataclass(frozen=True)
class MenuItem:
    id: str
    location: str
    date: str
    period: str
    station: str
    name: str
    serving_label: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    ingredients: list[str]
    allergens: list[str]
    source_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "location": self.location,
            "date": self.date,
            "period": self.period,
            "station": self.station,
            "name": self.name,
            "serving_label": self.serving_label,
            "calories": self.calories,
            "protein_g": self.protein_g,
            "carbs_g": self.carbs_g,
            "fat_g": self.fat_g,
            "ingredients": self.ingredients,
            "allergens": self.allergens,
            "source_hash": self.source_hash,
        }


@dataclass
class MenuDocument:
    location: str
    date: str
    status: str
    fetched_at: str
    periods: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    warning: str | None = None
    source: str = "playwright"

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "date": self.date,
            "status": self.status,
            "fetched_at": self.fetched_at,
            "warning": self.warning,
            "source": self.source,
            "periods": self.periods,
        }


class MenuProvider(ABC):
    @abstractmethod
    def fetch_menu(self, location: DiningLocationConfig, date: str) -> MenuDocument:
        raise NotImplementedError


class PlaywrightDiningProvider(MenuProvider):
    COMMON_PERIOD_NAMES = ("Breakfast", "Lunch", "Dinner", "Late Night", "Brunch")

    def __init__(self, *, timeout_ms: int = 20000, headless: bool = True):
        self.timeout_ms = timeout_ms
        self.headless = headless

    def fetch_menu(self, location: DiningLocationConfig, date: str) -> MenuDocument:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise MenuProviderDependencyError(
                "Playwright is not installed. Run `python3 -m playwright install chromium` after installing requirements."
            ) from exc

        with sync_playwright() as playwright:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
            if os.getenv("PLAYWRIGHT_DISABLE_SANDBOX", "").lower() in {"1", "true", "yes", "on"}:
                launch_args.append("--no-sandbox")
            browser = playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/134.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 960},
                locale="en-US",
            )
            context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4]});
                """
            )
            page = context.new_page()

            try:
                self._open_menu_page(page, location.menu_page_url, date)
                if self._page_is_blocked(page):
                    raise MenuSyncError("The dining site blocked the browser session before menu data could load.")

                self._select_location(page, location.name)
                available_periods = self._extract_available_periods(page)
                if not available_periods:
                    current_period = self._current_period_label(page)
                    available_periods = [current_period] if current_period else []

                period_docs: dict[str, list[dict[str, Any]]] = {}
                warnings = []

                for period_name in available_periods:
                    try:
                        self._select_period(page, period_name)
                        period_docs[period_name] = self._extract_period_items(
                            page=page,
                            location_name=location.name,
                            date=date,
                            period_name=period_name,
                        )
                    except MenuSyncError as exc:
                        warnings.append(f"{period_name}: {exc}")

                if period_docs:
                    warning = " ".join(warnings) or None
                    if not any(period_docs.values()):
                        warning = warning or "No published menu items were found for this date."
                    return MenuDocument(
                        location=location.name,
                        date=date,
                        status="fresh",
                        fetched_at=now_iso(),
                        periods=period_docs,
                        warning=warning,
                    )

                raise MenuSyncError("No published menu items were found for this date.")
            except PlaywrightTimeoutError as exc:
                raise MenuSyncError("Timed out while loading the dining menu in the browser.") from exc
            finally:
                context.close()
                browser.close()

    def _open_menu_page(self, page: Any, menu_page_url: str, date: str) -> None:
        page.goto(f"{menu_page_url}?date={date}", wait_until="domcontentloaded", timeout=self.timeout_ms)
        self._wait_for_menu_settle(page)

    def _wait_for_menu_settle(self, page: Any) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except Exception:
            pass
        page.wait_for_timeout(150)

    def _page_is_blocked(self, page: Any) -> bool:
        try:
            title = (page.title() or "").lower()
        except Exception:
            title = ""

        try:
            body_text = (page.locator("body").inner_text(timeout=2500) or "").lower()
        except Exception:
            body_text = ""

        markers = [
            "attention required",
            "cloudflare",
            "please enable cookies",
            "sorry, you have been blocked",
        ]
        haystack = f"{title}\n{body_text}"
        return any(marker in haystack for marker in markers)

    def _select_location(self, page: Any, location_name: str) -> None:
        button = self._find_trigger_button(page, control_id="location-listbox", label_pattern=r"^Location\b")
        current_label = self._button_value(button)
        if location_name in current_label:
            return

        button.click()
        page.wait_for_timeout(120)
        option = self._find_list_option(page, listbox_id="location-listbox", option_text=location_name)
        option.click()
        self._wait_for_menu_settle(page)

        if location_name not in self._button_value(button):
            raise MenuSyncError(f"Unable to switch the dining page to {location_name}.")

    def _extract_available_periods(self, page: Any) -> list[str]:
        button = self._find_trigger_button(page, control_id="period-listbox", label_pattern=r"^Menu\b")
        current_label = self._button_value(button)

        button.click()
        page.wait_for_timeout(120)

        listbox = page.locator("#period-listbox")
        if listbox.count():
            raw_texts = listbox.locator("li, [role='option'], button").all_inner_texts()
        else:
            raw_texts = page.locator("[role='option'], li").all_inner_texts()

        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        periods = []
        for text in raw_texts:
            normalized = self._period_name_from_text(text)
            if normalized and normalized not in periods:
                periods.append(normalized)

        normalized_current = self._period_name_from_text(current_label)
        if not periods and normalized_current:
            periods.append(normalized_current)

        return periods

    def _select_period(self, page: Any, period_name: str) -> None:
        if self._current_period_label(page) == period_name:
            return

        button = self._find_trigger_button(page, control_id="period-listbox", label_pattern=r"^Menu\b")
        button.click()
        page.wait_for_timeout(300)

        option = self._find_list_option(page, listbox_id="period-listbox", option_text=period_name)
        option.click()
        self._wait_for_menu_settle(page)

    def _current_period_label(self, page: Any) -> str:
        button = self._find_trigger_button(page, control_id="period-listbox", label_pattern=r"^Menu\b")
        return self._period_name_from_text(self._button_value(button)) or self._button_value(button)

    def _find_trigger_button(self, page: Any, *, control_id: str, label_pattern: str) -> Any:
        locator = page.locator(f"button[aria-controls='{control_id}']")
        if locator.count():
            return locator.first
        return page.get_by_role("button", name=re.compile(label_pattern, re.I)).first

    def _button_value(self, button: Any) -> str:
        text = button.inner_text().strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[-1]
        return text

    def _find_list_option(self, page: Any, *, listbox_id: str, option_text: str) -> Any:
        listbox = page.locator(f"#{listbox_id}")
        if listbox.count():
            option = listbox.get_by_text(option_text, exact=True)
            if option.count():
                return option.first

            candidates = listbox.locator("li, [role='option'], button")
            candidate_count = candidates.count()
            for index in range(candidate_count):
                candidate = candidates.nth(index)
                label = candidate.inner_text().strip()
                if self._period_name_from_text(label) == option_text:
                    return candidate

        option = page.get_by_text(option_text, exact=True)
        if option.count():
            return option.first

        raise MenuSyncError(f"Unable to find the option '{option_text}' in the dining selector.")

    def _period_name_from_text(self, text: str) -> str | None:
        clean = " ".join(str(text or "").split())
        if not clean:
            return None

        for period_name in self.COMMON_PERIOD_NAMES:
            pattern = re.compile(rf"\b{re.escape(period_name)}\b", re.I)
            if pattern.search(clean):
                return period_name

        return None

    def _extract_period_items(
        self,
        *,
        page: Any,
        location_name: str,
        date: str,
        period_name: str,
    ) -> list[dict[str, Any]]:
        tables = page.locator("table")
        table_count = tables.count()
        if table_count == 0:
            return []

        items = []
        seen: set[str] = set()

        for table_index in range(table_count):
            table = tables.nth(table_index)
            station = self._station_name_for_table(table) or "General"
            rows = table.locator("tbody tr")
            row_count = rows.count()

            for row_index in range(row_count):
                row = rows.nth(row_index)
                raw_summary = self._extract_row_summary(row)
                if raw_summary is None:
                    continue

                detail = self._extract_item_detail(page, row)
                merged = {**raw_summary, **detail}

                normalized = self._normalize_menu_item(
                    raw_item=merged,
                    location=location_name,
                    date=date,
                    period=period_name,
                    station=station,
                )
                if normalized.id in seen:
                    continue
                seen.add(normalized.id)
                items.append(normalized.to_dict())

        return items

    def _station_name_for_table(self, table: Any) -> str:
        station = table.evaluate(
            """
            (tableNode) => {
              const ignored = new Set(['Click any item for nutritional information.']);
              let node = tableNode.parentElement;
              while (node) {
                let sibling = node.previousElementSibling;
                while (sibling) {
                  const text = (sibling.innerText || '').trim();
                  if (text && !ignored.has(text)) {
                    return text.split('\\n')[0].trim();
                  }
                  sibling = sibling.previousElementSibling;
                }
                node = node.parentElement;
              }
              return 'General';
            }
            """
        )
        return str(station).strip() or "General"

    def _extract_row_summary(self, row: Any) -> dict[str, Any] | None:
        cells = row.locator("td")
        if cells.count() < 3:
            return None

        name_block = cells.nth(0).inner_text().strip()
        if not name_block:
            return None

        lines = [line.strip() for line in name_block.splitlines() if line.strip()]
        if not lines:
            return None

        return {
            "name": lines[0],
            "description": " ".join(lines[1:]),
            "portion": cells.nth(1).inner_text().strip() or "1 serving",
            "calories": self._safe_float(cells.nth(2).inner_text().strip()),
        }

    def _extract_item_detail(self, page: Any, row: Any) -> dict[str, Any]:
        button = row.locator("button[aria-label*='View nutritional information']")
        if button.count() == 0:
            return {}

        button.first.click()
        dialog = page.locator("[role='dialog']").last
        dialog.wait_for(state="visible", timeout=self.timeout_ms)
        dialog_text = dialog.inner_text(timeout=5000)
        detail = self._parse_dialog_text(dialog_text)

        close_button = dialog.get_by_role("button", name="Close")
        if close_button.count():
            close_button.first.click()
        else:
            page.keyboard.press("Escape")

        try:
            dialog.wait_for(state="hidden", timeout=5000)
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

        page.wait_for_timeout(40)
        return detail

    def _parse_dialog_text(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        ingredients = []
        allergens = []

        ingredient_match = re.search(r"Ingredients:\s*(.+?)(?:Disclaimer:|Allergens?:|Close|$)", cleaned, re.S | re.I)
        if ingredient_match:
            ingredients = self._string_list(ingredient_match.group(1).replace("\n", " "))

        allergen_match = re.search(r"Allergens?:\s*(.+?)(?:Disclaimer:|Close|$)", cleaned, re.S | re.I)
        if allergen_match:
            allergens = self._string_list(allergen_match.group(1).replace("\n", " "))

        return {
            "portion": self._first_match(cleaned, r"Serving size:\s*(.+?)(?:\n|$)", cast="text"),
            "calories": self._first_match(cleaned, r"Calories\s*([0-9]+(?:\.[0-9]+)?)"),
            "protein_g": self._first_match(cleaned, r"Protein \(g\)\s*([0-9]+(?:\.[0-9]+)?)"),
            "carbs_g": self._first_match(cleaned, r"Total Carbohydrates? \(g\)\s*([0-9]+(?:\.[0-9]+)?)"),
            "fat_g": self._first_match(cleaned, r"Total Fat \(g\)\s*([0-9]+(?:\.[0-9]+)?)"),
            "ingredients": ingredients,
            "allergens": allergens,
        }

    def _first_match(self, text: str, pattern: str, *, cast: str = "float") -> Any:
        match = re.search(pattern, text, re.I)
        if not match:
            return "" if cast == "text" else 0.0
        value = match.group(1).strip()
        if cast == "text":
            return value
        return self._safe_float(value)

    def _parse_periods_response(self, payload: Any) -> list[dict[str, str]]:
        period_list = None
        if isinstance(payload, dict) and isinstance(payload.get("periods"), list):
            period_list = payload["periods"]
        elif isinstance(payload, dict):
            period_list = self._find_first_list_for_key(payload, "periods")

        if not isinstance(period_list, list):
            return []

        periods = []
        for item in period_list:
            if not isinstance(item, dict):
                continue
            period_id = item.get("id") or item.get("_id")
            period_name = item.get("name") or item.get("label") or item.get("title")
            if period_id and period_name:
                periods.append({"id": str(period_id), "name": str(period_name)})
        return periods

    def _parse_menu_payload(
        self,
        payload: Any,
        location_name: str,
        date: str,
        period_name: str,
    ) -> list[dict[str, Any]]:
        categories = self._find_category_nodes(payload)
        normalized_items: list[dict[str, Any]] = []
        seen: set[str] = set()

        for category in categories:
            station = (
                category.get("name")
                or category.get("title")
                or category.get("station")
                or category.get("label")
                or "General"
            )
            for item in category.get("items", []):
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_menu_item(
                    raw_item=item,
                    location=location_name,
                    date=date,
                    period=period_name,
                    station=str(station),
                )
                if normalized.id in seen:
                    continue
                seen.add(normalized.id)
                normalized_items.append(normalized.to_dict())

        if normalized_items:
            return normalized_items

        direct_items = []
        for item in self._find_item_nodes(payload):
            normalized = self._normalize_menu_item(
                raw_item=item,
                location=location_name,
                date=date,
                period=period_name,
                station="General",
            )
            if normalized.id in seen:
                continue
            seen.add(normalized.id)
            direct_items.append(normalized.to_dict())
        return direct_items

    def _find_first_list_for_key(self, payload: Any, target_key: str) -> list[Any] | None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key == target_key and isinstance(value, list):
                    return value
                nested = self._find_first_list_for_key(value, target_key)
                if nested is not None:
                    return nested
        elif isinstance(payload, list):
            for item in payload:
                nested = self._find_first_list_for_key(item, target_key)
                if nested is not None:
                    return nested
        return None

    def _find_category_nodes(self, payload: Any) -> list[dict[str, Any]]:
        categories = []
        if isinstance(payload, dict):
            if isinstance(payload.get("items"), list):
                categories.append(payload)
            for value in payload.values():
                categories.extend(self._find_category_nodes(value))
        elif isinstance(payload, list):
            for item in payload:
                categories.extend(self._find_category_nodes(item))
        return categories

    def _find_item_nodes(self, payload: Any) -> list[dict[str, Any]]:
        items = []
        if isinstance(payload, dict):
            if self._looks_like_menu_item(payload):
                items.append(payload)
            for value in payload.values():
                items.extend(self._find_item_nodes(value))
        elif isinstance(payload, list):
            for item in payload:
                items.extend(self._find_item_nodes(item))
        return items

    def _looks_like_menu_item(self, payload: dict[str, Any]) -> bool:
        name = payload.get("name") or payload.get("label")
        has_nutrition = (
            "calories" in payload
            or "nutrients" in payload
            or "nutrition" in payload
            or "portion" in payload
        )
        return bool(name and has_nutrition)

    def _normalize_menu_item(
        self,
        *,
        raw_item: dict[str, Any],
        location: str,
        date: str,
        period: str,
        station: str,
    ) -> MenuItem:
        name = str(raw_item.get("name") or raw_item.get("label") or "Unknown item").strip()
        serving_label = self._extract_serving_label(raw_item)
        nutrients = self._extract_nutrients(raw_item)
        calories = self._safe_float(raw_item.get("calories", nutrients.get("calories", 0)))
        ingredients = self._string_list(raw_item.get("ingredients"))
        allergens = self._extract_allergens(raw_item)

        source_payload = {
            "location": location,
            "date": date,
            "period": period,
            "station": station,
            "name": name,
            "serving_label": serving_label,
            "calories": calories,
            "protein_g": nutrients.get("protein_g", 0),
            "carbs_g": nutrients.get("carbs_g", 0),
            "fat_g": nutrients.get("fat_g", 0),
        }
        source_hash = hashlib.sha256(json.dumps(source_payload, sort_keys=True).encode("utf-8")).hexdigest()

        return MenuItem(
            id=source_hash,
            location=location,
            date=date,
            period=period,
            station=station,
            name=name,
            serving_label=serving_label,
            calories=calories,
            protein_g=self._safe_float(nutrients.get("protein_g", 0)),
            carbs_g=self._safe_float(nutrients.get("carbs_g", 0)),
            fat_g=self._safe_float(nutrients.get("fat_g", 0)),
            ingredients=ingredients,
            allergens=allergens,
            source_hash=source_hash,
        )

    def _extract_serving_label(self, raw_item: dict[str, Any]) -> str:
        candidates = [
            raw_item.get("portion"),
            raw_item.get("serving_label"),
            raw_item.get("serving_size"),
            raw_item.get("servingSize"),
            raw_item.get("portion_size"),
            raw_item.get("serving"),
        ]
        for candidate in candidates:
            if candidate:
                return str(candidate).strip()
        return "1 serving"

    def _extract_nutrients(self, raw_item: dict[str, Any]) -> dict[str, float]:
        direct = {
            "protein_g": self._safe_float(raw_item.get("protein_g", 0)),
            "carbs_g": self._safe_float(raw_item.get("carbs_g", 0)),
            "fat_g": self._safe_float(raw_item.get("fat_g", 0)),
            "calories": self._safe_float(raw_item.get("calories", 0)),
        }

        raw_nutrients = raw_item.get("nutrients") or raw_item.get("nutrition") or raw_item.get("nutritional_info") or []
        nutrient_map: dict[str, float] = {}

        if isinstance(raw_nutrients, list):
            for nutrient in raw_nutrients:
                if not isinstance(nutrient, dict):
                    continue
                raw_name = nutrient.get("name") or nutrient.get("label") or nutrient.get("title")
                if not raw_name:
                    continue
                nutrient_map[str(raw_name).strip().lower()] = self._safe_float(
                    nutrient.get("value_numeric") or nutrient.get("value") or nutrient.get("amount") or 0
                )
        elif isinstance(raw_nutrients, dict):
            for key, value in raw_nutrients.items():
                nutrient_map[str(key).strip().lower()] = self._safe_float(value)
        elif isinstance(raw_nutrients, str):
            nutrient_map.update(self._extract_nutrients_from_text(raw_nutrients))

        result = {
            "protein_g": direct["protein_g"] or self._first_nutrient_match(nutrient_map, ["protein"]),
            "carbs_g": direct["carbs_g"] or self._first_nutrient_match(nutrient_map, ["total carbohydrate", "carbohydrate", "carbs"]),
            "fat_g": direct["fat_g"] or self._first_nutrient_match(nutrient_map, ["total fat", "fat"]),
            "calories": direct["calories"] or self._first_nutrient_match(nutrient_map, ["calories", "calorie", "energy"]),
        }
        return result

    def _extract_nutrients_from_text(self, text: str) -> dict[str, float]:
        lower = text.lower()
        return {
            "protein": self._regex_number(lower, r"protein[^0-9]*(\d+(?:\.\d+)?)"),
            "carbohydrate": self._regex_number(lower, r"(?:carbs?|carbohydrate)[^0-9]*(\d+(?:\.\d+)?)"),
            "fat": self._regex_number(lower, r"fat[^0-9]*(\d+(?:\.\d+)?)"),
            "calories": self._regex_number(lower, r"calories?[^0-9]*(\d+(?:\.\d+)?)"),
        }

    def _regex_number(self, text: str, pattern: str) -> float:
        match = re.search(pattern, text)
        return self._safe_float(match.group(1)) if match else 0.0

    def _first_nutrient_match(self, nutrients: dict[str, float], keys: list[str]) -> float:
        for key in keys:
            for nutrient_name, value in nutrients.items():
                if key in nutrient_name:
                    return value
        return 0.0

    def _string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, dict):
            flattened = []
            for item in value.values():
                flattened.extend(self._string_list(item))
            return flattened
        if isinstance(value, str):
            parts = [part.strip() for part in re.split(r",|;", value) if part.strip()]
            return parts
        return [str(value).strip()]

    def _extract_allergens(self, raw_item: dict[str, Any]) -> list[str]:
        candidates = [
            raw_item.get("allergens"),
            raw_item.get("allergen"),
            raw_item.get("allergen_text"),
            raw_item.get("labels"),
        ]
        allergens = []
        for candidate in candidates:
            allergens.extend(self._string_list(candidate))
        return sorted({value for value in allergens if value})

    def _safe_float(self, value: Any) -> float:
        try:
            return round(float(str(value).replace("g", "").replace("mg", "").strip()), 2)
        except (TypeError, ValueError):
            return 0.0
