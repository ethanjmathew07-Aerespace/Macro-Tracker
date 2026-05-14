from __future__ import annotations

from copy import deepcopy
from typing import Any

from fast_food_catalog import FAST_FOOD_RESTAURANTS
from storage import SQLiteRepository, ValidationError, coerce_float


class FastFoodService:
    def __init__(self, repository: SQLiteRepository, catalog: list[dict[str, Any]] | None = None):
        self.repository = repository
        self.catalog = deepcopy(catalog or FAST_FOOD_RESTAURANTS)
        self._items_by_id = {}
        for restaurant in self.catalog:
            for item in restaurant.get("items", []):
                self._items_by_id[item["id"]] = {
                    "restaurant_slug": restaurant["slug"],
                    "restaurant_name": restaurant["name"],
                    "source": restaurant.get("source", ""),
                    **item,
                }

    def get_catalog(self) -> dict[str, Any]:
        return {
            "restaurants": [
                {**restaurant, "item_count": len(restaurant.get("items", []))}
                for restaurant in self.catalog
            ]
        }

    def log_item(self, *, item_id: str, date: str, servings: Any = 1.0) -> dict[str, Any]:
        item = self._items_by_id.get(str(item_id).strip())
        if item is None:
            raise ValidationError("Fast food item not found.")

        normalized_servings = coerce_float(servings, field_name="servings", minimum=0.01)
        return self.repository.add_meal_entry(
            entry_date=date,
            name=f'{item["restaurant_name"]} - {item["name"]}',
            protein_g=round(item["protein_g"] * normalized_servings, 2),
            carbs_g=round(item["carbs_g"] * normalized_servings, 2),
            fat_g=round(item["fat_g"] * normalized_servings, 2),
            calories=round(item["calories"] * normalized_servings, 2),
            source="fast_food",
            servings=normalized_servings,
            menu_item_id=item["id"],
        )
