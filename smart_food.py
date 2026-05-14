from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FoodReference:
    name: str
    aliases: tuple[str, ...]
    calories_per_gram: float
    protein_per_gram: float
    carbs_per_gram: float
    fat_per_gram: float
    grams_by_unit: dict[str, float]


FOOD_REFERENCES = [
    FoodReference(
        name="Chicken Breast",
        aliases=("chicken breast", "grilled chicken", "chicken"),
        calories_per_gram=1.65,
        protein_per_gram=0.31,
        carbs_per_gram=0.0,
        fat_per_gram=0.036,
        grams_by_unit={"serving": 120, "piece": 120, "oz": 28.35},
    ),
    FoodReference(
        name="Ground Beef 90/10",
        aliases=("ground beef", "lean beef", "beef"),
        calories_per_gram=1.76,
        protein_per_gram=0.26,
        carbs_per_gram=0.0,
        fat_per_gram=0.10,
        grams_by_unit={"serving": 113, "oz": 28.35},
    ),
    FoodReference(
        name="Salmon",
        aliases=("salmon", "fish"),
        calories_per_gram=2.08,
        protein_per_gram=0.20,
        carbs_per_gram=0.0,
        fat_per_gram=0.13,
        grams_by_unit={"serving": 113, "oz": 28.35},
    ),
    FoodReference(
        name="White Rice",
        aliases=("white rice", "rice"),
        calories_per_gram=1.30,
        protein_per_gram=0.027,
        carbs_per_gram=0.282,
        fat_per_gram=0.003,
        grams_by_unit={"cup": 158, "serving": 158, "oz": 28.35},
    ),
    FoodReference(
        name="Brown Rice",
        aliases=("brown rice",),
        calories_per_gram=1.23,
        protein_per_gram=0.026,
        carbs_per_gram=0.255,
        fat_per_gram=0.01,
        grams_by_unit={"cup": 195, "serving": 195, "oz": 28.35},
    ),
    FoodReference(
        name="Cooked Pasta",
        aliases=("pasta", "spaghetti", "penne", "macaroni"),
        calories_per_gram=1.58,
        protein_per_gram=0.058,
        carbs_per_gram=0.306,
        fat_per_gram=0.009,
        grams_by_unit={"cup": 140, "serving": 140, "oz": 28.35},
    ),
    FoodReference(
        name="Oats",
        aliases=("oats", "oatmeal"),
        calories_per_gram=3.89,
        protein_per_gram=0.169,
        carbs_per_gram=0.663,
        fat_per_gram=0.069,
        grams_by_unit={"cup": 80, "serving": 40, "oz": 28.35},
    ),
    FoodReference(
        name="Banana",
        aliases=("banana",),
        calories_per_gram=0.89,
        protein_per_gram=0.011,
        carbs_per_gram=0.228,
        fat_per_gram=0.003,
        grams_by_unit={"banana": 118, "piece": 118, "serving": 118},
    ),
    FoodReference(
        name="Apple",
        aliases=("apple",),
        calories_per_gram=0.52,
        protein_per_gram=0.003,
        carbs_per_gram=0.14,
        fat_per_gram=0.002,
        grams_by_unit={"apple": 182, "piece": 182, "serving": 182},
    ),
    FoodReference(
        name="Egg",
        aliases=("egg", "eggs"),
        calories_per_gram=1.43,
        protein_per_gram=0.126,
        carbs_per_gram=0.007,
        fat_per_gram=0.095,
        grams_by_unit={"egg": 50, "piece": 50, "serving": 50},
    ),
    FoodReference(
        name="Greek Yogurt",
        aliases=("greek yogurt", "yogurt"),
        calories_per_gram=0.97,
        protein_per_gram=0.10,
        carbs_per_gram=0.036,
        fat_per_gram=0.04,
        grams_by_unit={"cup": 245, "serving": 170, "oz": 28.35},
    ),
    FoodReference(
        name="Peanut Butter",
        aliases=("peanut butter",),
        calories_per_gram=5.88,
        protein_per_gram=0.25,
        carbs_per_gram=0.20,
        fat_per_gram=0.50,
        grams_by_unit={"tbsp": 16, "serving": 32, "oz": 28.35},
    ),
    FoodReference(
        name="Potato",
        aliases=("potato", "potatoes"),
        calories_per_gram=0.77,
        protein_per_gram=0.02,
        carbs_per_gram=0.17,
        fat_per_gram=0.001,
        grams_by_unit={"potato": 173, "piece": 173, "cup": 150},
    ),
    FoodReference(
        name="Avocado",
        aliases=("avocado",),
        calories_per_gram=1.60,
        protein_per_gram=0.02,
        carbs_per_gram=0.085,
        fat_per_gram=0.147,
        grams_by_unit={"avocado": 150, "piece": 150, "serving": 50},
    ),
    FoodReference(
        name="Bread",
        aliases=("bread", "toast"),
        calories_per_gram=2.65,
        protein_per_gram=0.09,
        carbs_per_gram=0.49,
        fat_per_gram=0.032,
        grams_by_unit={"slice": 28, "piece": 28, "serving": 28},
    ),
    FoodReference(
        name="Cheddar Cheese",
        aliases=("cheese", "cheddar"),
        calories_per_gram=4.03,
        protein_per_gram=0.249,
        carbs_per_gram=0.013,
        fat_per_gram=0.332,
        grams_by_unit={"slice": 28, "serving": 28, "oz": 28.35},
    ),
    FoodReference(
        name="Milk",
        aliases=("milk",),
        calories_per_gram=0.61,
        protein_per_gram=0.032,
        carbs_per_gram=0.048,
        fat_per_gram=0.033,
        grams_by_unit={"cup": 244, "serving": 244},
    ),
    FoodReference(
        name="Protein Bar",
        aliases=("protein bar", "bar"),
        calories_per_gram=3.83,
        protein_per_gram=0.33,
        carbs_per_gram=0.40,
        fat_per_gram=0.117,
        grams_by_unit={"bar": 60, "piece": 60, "serving": 60},
    ),
]


UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "cup": "cup",
    "cups": "cup",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "slice": "slice",
    "slices": "slice",
    "piece": "piece",
    "pieces": "piece",
    "serving": "serving",
    "servings": "serving",
    "banana": "banana",
    "bananas": "banana",
    "apple": "apple",
    "apples": "apple",
    "egg": "egg",
    "eggs": "egg",
    "bar": "bar",
    "bars": "bar",
    "potato": "potato",
    "potatoes": "potato",
    "avocado": "avocado",
    "avocados": "avocado",
}


CALORIE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:k?cal|calories?|cals?)\b", re.I)
AMOUNT_PATTERN = re.compile(
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>g|grams?|kg|oz|ounces?|lbs?|pounds?|cups?|tbsp|tablespoons?|tsp|teaspoons?|slices?|pieces?|servings?|bananas?|apples?|eggs?|bars?|potatoes?|avocados?)\b",
    re.I,
)


def _round(value: float) -> float:
    return round(value, 1)


class SmartFoodService:
    def estimate_from_text(self, *, query: str, known_calories: Any | None = None) -> dict[str, Any]:
        raw_query = str(query or "").strip()
        if not raw_query:
            raise ValueError("Food description is required.")

        explicit_calories = _coerce_optional_float(known_calories)
        if explicit_calories is None:
            calorie_match = CALORIE_PATTERN.search(raw_query)
            if calorie_match:
                explicit_calories = float(calorie_match.group("value"))

        amount_match = AMOUNT_PATTERN.search(raw_query)
        amount = float(amount_match.group("amount")) if amount_match else 1.0
        unit = UNIT_ALIASES.get((amount_match.group("unit") if amount_match else "serving").lower(), "serving")

        reference = self._match_food_reference(raw_query)
        cleaned_name = self._clean_food_name(raw_query)

        if reference is None:
            calories = explicit_calories or 0.0
            return {
                "name": cleaned_name or "Custom food",
                "serving_amount": amount,
                "serving_unit": unit,
                "calories": _round(calories),
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "notes": "No food match yet, so this first draft kept macros at zero. You can edit before saving.",
                "confidence": "low",
                "source": "assistant_text",
            }

        grams = self._grams_for(reference, amount, unit)
        estimated = {
            "name": reference.name,
            "serving_amount": amount,
            "serving_unit": unit,
            "calories": grams * reference.calories_per_gram,
            "protein_g": grams * reference.protein_per_gram,
            "carbs_g": grams * reference.carbs_per_gram,
            "fat_g": grams * reference.fat_per_gram,
            "notes": f"Estimated from {amount:g} {unit} of {reference.name.lower()}.",
            "confidence": "medium",
            "source": "assistant_text",
        }

        if explicit_calories is not None and estimated["calories"] > 0:
            scale = explicit_calories / estimated["calories"]
            estimated["calories"] = explicit_calories
            estimated["protein_g"] *= scale
            estimated["carbs_g"] *= scale
            estimated["fat_g"] *= scale
            estimated["notes"] = (
                f"Matched {reference.name.lower()} and scaled macros to your provided {explicit_calories:g} calories."
            )
            estimated["confidence"] = "medium-high"

        estimated["calories"] = _round(estimated["calories"])
        estimated["protein_g"] = _round(estimated["protein_g"])
        estimated["carbs_g"] = _round(estimated["carbs_g"])
        estimated["fat_g"] = _round(estimated["fat_g"])
        return estimated

    def _match_food_reference(self, query: str) -> FoodReference | None:
        lowered = query.lower()
        for reference in FOOD_REFERENCES:
            if any(alias in lowered for alias in reference.aliases):
                return reference
        return None

    def _clean_food_name(self, query: str) -> str:
        cleaned = CALORIE_PATTERN.sub("", query)
        cleaned = AMOUNT_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        return cleaned.title()

    def _grams_for(self, reference: FoodReference, amount: float, unit: str) -> float:
        if unit == "g":
            return amount
        if unit == "kg":
            return amount * 1000
        if unit == "oz":
            return amount * 28.35
        if unit == "lb":
            return amount * 453.592
        if unit == "tbsp":
            return amount * reference.grams_by_unit.get("tbsp", 15)
        if unit == "tsp":
            return amount * reference.grams_by_unit.get("tsp", 5)

        base = reference.grams_by_unit.get(unit) or reference.grams_by_unit.get("serving") or 100
        return amount * base


def _coerce_optional_float(value: Any | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


class NutritionLabelService:
    def __init__(self, *, swift_script_path: str | Path):
        self.swift_script_path = Path(swift_script_path)

    def parse_uploaded_label(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        fallback_name: str | None = None,
        fallback_brand: str | None = None,
    ) -> dict[str, Any]:
        suffix = Path(filename or "label.jpg").suffix or ".jpg"
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / f"label{suffix}"
            image_path.write_bytes(image_bytes)
            ocr_text = self._extract_text(image_path)

        parsed = self.parse_label_text(ocr_text, fallback_name=fallback_name, fallback_brand=fallback_brand)
        parsed["ocr_text"] = ocr_text
        return parsed

    def _extract_text(self, image_path: Path) -> str:
        if not self.swift_script_path.exists():
            raise RuntimeError("The macOS OCR helper script is missing.")

        try:
            result = subprocess.run(
                ["/usr/bin/swift", str(self.swift_script_path), str(image_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Label scan timed out before text could be extracted.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or "The OCR helper failed."
            raise RuntimeError(message) from exc

        text = result.stdout.strip()
        if not text:
            raise RuntimeError("No text could be read from that label photo.")
        return text

    def parse_label_text(
        self,
        text: str,
        *,
        fallback_name: str | None = None,
        fallback_brand: str | None = None,
    ) -> dict[str, Any]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("No text could be parsed from that label.")

        serving_size = self._extract_text_value(text, [r"serving size[:\s]+([^\n]+)"])
        calories = self._extract_number(text, [r"\bcalories\b[:\s]+(\d+(?:\.\d+)?)", r"\bcalories\s+(\d+(?:\.\d+)?)"])
        protein = self._extract_number(text, [r"\bprotein\b[:\s]+(\d+(?:\.\d+)?)"])
        carbs = self._extract_number(
            text,
            [r"\btotal carbohydrate[s]?\b[:\s]+(\d+(?:\.\d+)?)", r"\bcarb[s]?\b[:\s]+(\d+(?:\.\d+)?)"],
        )
        fat = self._extract_number(text, [r"\btotal fat\b[:\s]+(\d+(?:\.\d+)?)", r"\bfat\b[:\s]+(\d+(?:\.\d+)?)"])

        title_candidates = [
            line
            for line in lines[:6]
            if "nutrition" not in line.lower() and "serving" not in line.lower() and len(line) <= 80
        ]
        display_name = (fallback_name or (title_candidates[0] if title_candidates else "Scanned Item")).strip()

        return {
            "name": display_name.title(),
            "brand": (fallback_brand or "").strip(),
            "serving_label": serving_size or "1 serving",
            "serving_amount": 1.0,
            "serving_unit": "serving",
            "calories": _round(calories),
            "protein_g": _round(protein),
            "carbs_g": _round(carbs),
            "fat_g": _round(fat),
            "notes": "Parsed from a nutrition label photo.",
            "confidence": "medium",
            "source": "label_scan",
        }

    def _extract_number(self, text: str, patterns: list[str]) -> float:
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return float(match.group(1))
        return 0.0

    def _extract_text_value(self, text: str, patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1).strip()
        return ""


def serialize_estimate(estimate: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(estimate))
