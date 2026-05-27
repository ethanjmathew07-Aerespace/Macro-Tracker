from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class FoodReference:
    name: str
    aliases: tuple[str, ...]
    calories_per_gram: float
    protein_per_gram: float
    carbs_per_gram: float
    fat_per_gram: float
    grams_by_unit: dict[str, float]


@dataclass(frozen=True)
class MatchedFood:
    reference: FoodReference
    alias: str
    start: int
    end: int
    amount: float
    unit: str


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
        grams_by_unit={"cup": 158, "bowl": 200, "serving": 158, "oz": 28.35},
    ),
    FoodReference(
        name="Brown Rice",
        aliases=("brown rice",),
        calories_per_gram=1.23,
        protein_per_gram=0.026,
        carbs_per_gram=0.255,
        fat_per_gram=0.01,
        grams_by_unit={"cup": 195, "bowl": 220, "serving": 195, "oz": 28.35},
    ),
    FoodReference(
        name="Cooked Pasta",
        aliases=("pasta", "spaghetti", "penne", "macaroni"),
        calories_per_gram=1.58,
        protein_per_gram=0.058,
        carbs_per_gram=0.306,
        fat_per_gram=0.009,
        grams_by_unit={"cup": 140, "bowl": 190, "serving": 140, "oz": 28.35},
    ),
    FoodReference(
        name="Black Beans",
        aliases=("black beans", "beans"),
        calories_per_gram=1.32,
        protein_per_gram=0.089,
        carbs_per_gram=0.237,
        fat_per_gram=0.005,
        grams_by_unit={"cup": 172, "serving": 130},
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
        grams_by_unit={"cup": 245, "container": 170, "serving": 170, "oz": 28.35},
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
        grams_by_unit={"cup": 244, "bottle": 355, "serving": 244},
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
    FoodReference(
        name="Protein Shake",
        aliases=("protein shake", "shake"),
        calories_per_gram=0.73,
        protein_per_gram=0.073,
        carbs_per_gram=0.024,
        fat_per_gram=0.012,
        grams_by_unit={"bottle": 414, "container": 325, "serving": 325},
    ),
    FoodReference(
        name="Whey Protein",
        aliases=("whey protein", "protein powder"),
        calories_per_gram=4.0,
        protein_per_gram=0.80,
        carbs_per_gram=0.10,
        fat_per_gram=0.07,
        grams_by_unit={"scoop": 31, "serving": 31},
    ),
    FoodReference(
        name="Tortilla",
        aliases=("tortilla", "wrap"),
        calories_per_gram=3.10,
        protein_per_gram=0.085,
        carbs_per_gram=0.52,
        fat_per_gram=0.08,
        grams_by_unit={"piece": 50, "wrap": 70, "serving": 50},
    ),
    FoodReference(
        name="Olive Oil",
        aliases=("olive oil", "oil"),
        calories_per_gram=8.84,
        protein_per_gram=0.0,
        carbs_per_gram=0.0,
        fat_per_gram=1.0,
        grams_by_unit={"tbsp": 13.5, "tsp": 4.5, "serving": 13.5},
    ),
    FoodReference(
        name="Broccoli",
        aliases=("broccoli",),
        calories_per_gram=0.35,
        protein_per_gram=0.024,
        carbs_per_gram=0.072,
        fat_per_gram=0.004,
        grams_by_unit={"cup": 91, "serving": 91},
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
    "scoop": "scoop",
    "scoops": "scoop",
    "bottle": "bottle",
    "bottles": "bottle",
    "container": "container",
    "containers": "container",
    "wrap": "wrap",
    "wraps": "wrap",
    "bowl": "bowl",
    "bowls": "bowl",
    "can": "can",
    "cans": "can",
}


CALORIE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:k?cal|calories?|cals?)\b", re.I)
AMOUNT_PATTERN = re.compile(
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>g|grams?|kg|oz|ounces?|lbs?|pounds?|cups?|tbsp|tablespoons?|tsp|teaspoons?|slices?|pieces?|servings?|bananas?|apples?|eggs?|bars?|potatoes?|avocados?|scoops?|bottles?|containers?|wraps?|bowls?|cans?)\b",
    re.I,
)
SERVING_SIZE_PATTERN = re.compile(r"\bserv(?:ing)?\s*size\b[:\s]*([^\n\r]+)", re.I)
PERCENT_DV_PATTERN = re.compile(r"\d+\s*%")
NON_NAME_TOKENS = {
    "nutrition",
    "facts",
    "fact",
    "serving",
    "servings",
    "amount",
    "calories",
    "daily",
    "value",
    "total",
    "includes",
    "added",
}


def _round(value: float) -> float:
    return round(max(0.0, value), 1)


class OpenAINutritionClient:
    def __init__(self, *, api_key: str | None = None, model: str | None = None):
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = (model or os.getenv("OPENAI_MODEL", "gpt-5.1")).strip() or "gpt-5.1"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def estimate_from_text(self, *, query: str, known_calories: Any | None = None) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("OpenAI is not configured.")

        known_calorie_text = f"{known_calories}".strip() if known_calories not in {None, ''} else "not provided"
        response = self._responses_create(
            {
                "model": self.model,
                "reasoning": {"effort": "medium"},
                "max_output_tokens": 900,
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "You are a nutrition coach. Estimate calories, protein, carbs, and fat for a meal "
                                    "from a user's description. Think carefully about portions and typical restaurant "
                                    "or homemade serving sizes. If the user supplies calories, respect them and scale "
                                    "the macros to fit. Return only the requested structured data."
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    f"Meal description: {query}\n"
                                    f"Known calories: {known_calorie_text}\n"
                                    "Return a practical estimate with a concise explanation."
                                ),
                            }
                        ],
                    },
                ],
                "text": {"format": self._estimate_schema()},
            }
        )
        return self._normalize_estimate(self._extract_output_json(response), source="assistant_text")

    def parse_label(
        self,
        *,
        image_bytes: bytes,
        filename: str,
        ocr_text: str,
        fallback_name: str | None = None,
        fallback_brand: str | None = None,
    ) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("OpenAI is not configured.")

        suffix = (Path(filename).suffix or ".jpg").lstrip(".").lower()
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(suffix, "image/jpeg")
        data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

        fallback_bits = []
        if fallback_name:
            fallback_bits.append(f"Preferred item name: {fallback_name}")
        if fallback_brand:
            fallback_bits.append(f"Preferred brand: {fallback_brand}")

        response = self._responses_create(
            {
                "model": self.model,
                "reasoning": {"effort": "medium"},
                "max_output_tokens": 1000,
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "You are parsing a packaged food nutrition label. Use both the label image and OCR "
                                    "text to recover calories, protein, carbs, fat, and serving details as accurately as possible. "
                                    "If OCR conflicts with the image, trust the image. Return only the requested structured data."
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "\n".join(filter(None, fallback_bits)) or "No preferred name or brand."},
                            {"type": "input_text", "text": f"OCR text:\n{ocr_text}"},
                            {"type": "input_image", "image_url": data_url, "detail": "high"},
                        ],
                    },
                ],
                "text": {"format": self._label_schema()},
            }
        )
        return self._normalize_estimate(self._extract_output_json(response), source="label_scan")

    def _responses_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("OpenAI request failed before the model could respond.") from exc

    def _extract_output_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidate = payload.get("output_text")
        if not candidate:
            for item in payload.get("output", []):
                if item.get("type") != "message":
                    continue
                for content in item.get("content", []):
                    text_value = content.get("text")
                    if text_value:
                        candidate = text_value
                        break
                if candidate:
                    break
        if isinstance(candidate, dict):
            return candidate
        if not isinstance(candidate, str) or not candidate.strip():
            raise RuntimeError("OpenAI returned an empty nutrition response.")
        return json.loads(candidate)

    def _normalize_estimate(self, payload: dict[str, Any], *, source: str) -> dict[str, Any]:
        serving_amount = _coerce_optional_float(payload.get("serving_amount")) or 1.0
        serving_unit = str(payload.get("serving_unit") or "serving").strip() or "serving"
        calories = _coerce_optional_float(payload.get("calories")) or 0.0
        protein = _coerce_optional_float(payload.get("protein_g")) or 0.0
        carbs = _coerce_optional_float(payload.get("carbs_g")) or 0.0
        fat = _coerce_optional_float(payload.get("fat_g")) or 0.0

        if calories <= 0 and any(value > 0 for value in (protein, carbs, fat)):
            calories = protein * 4 + carbs * 4 + fat * 9

        return {
            "name": str(payload.get("name") or "Estimated Food").strip() or "Estimated Food",
            "brand": str(payload.get("brand") or "").strip(),
            "serving_label": str(payload.get("serving_label") or "").strip(),
            "serving_amount": _round(serving_amount),
            "serving_unit": serving_unit,
            "calories": _round(calories),
            "protein_g": _round(protein),
            "carbs_g": _round(carbs),
            "fat_g": _round(fat),
            "notes": str(payload.get("notes") or "").strip(),
            "assistant_message": str(payload.get("assistant_message") or "").strip()
            or "I estimated the nutrition from the details you provided.",
            "confidence": str(payload.get("confidence") or "medium").strip() or "medium",
            "source": source,
        }

    def _estimate_schema(self) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "name": "nutrition_estimate",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "brand": {"type": "string"},
                    "serving_amount": {"type": "number"},
                    "serving_unit": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fat_g": {"type": "number"},
                    "notes": {"type": "string"},
                    "assistant_message": {"type": "string"},
                    "confidence": {"type": "string"},
                },
                "required": [
                    "name",
                    "brand",
                    "serving_amount",
                    "serving_unit",
                    "calories",
                    "protein_g",
                    "carbs_g",
                    "fat_g",
                    "notes",
                    "assistant_message",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        }

    def _label_schema(self) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "name": "nutrition_label_parse",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "brand": {"type": "string"},
                    "serving_label": {"type": "string"},
                    "serving_amount": {"type": "number"},
                    "serving_unit": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fat_g": {"type": "number"},
                    "notes": {"type": "string"},
                    "assistant_message": {"type": "string"},
                    "confidence": {"type": "string"},
                },
                "required": [
                    "name",
                    "brand",
                    "serving_label",
                    "serving_amount",
                    "serving_unit",
                    "calories",
                    "protein_g",
                    "carbs_g",
                    "fat_g",
                    "notes",
                    "assistant_message",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        }


class SmartFoodService:
    def __init__(self, *, openai_client: OpenAINutritionClient | None = None):
        self.openai_client = openai_client or OpenAINutritionClient()
        self.alias_entries = sorted(
            [(alias, reference) for reference in FOOD_REFERENCES for alias in reference.aliases],
            key=lambda item: len(item[0]),
            reverse=True,
        )

    def estimate_from_text(self, *, query: str, known_calories: Any | None = None) -> dict[str, Any]:
        raw_query = str(query or "").strip()
        if not raw_query:
            raise ValueError("Food description is required.")

        if self.openai_client.available:
            try:
                return self.openai_client.estimate_from_text(query=raw_query, known_calories=known_calories)
            except RuntimeError:
                pass

        return self._estimate_with_references(query=raw_query, known_calories=known_calories)

    def _estimate_with_references(self, *, query: str, known_calories: Any | None = None) -> dict[str, Any]:
        explicit_calories = _coerce_optional_float(known_calories)
        if explicit_calories is None:
            calorie_match = CALORIE_PATTERN.search(query)
            if calorie_match:
                explicit_calories = float(calorie_match.group("value"))

        matches = self._match_food_references(query)
        cleaned_name = self._clean_food_name(query) or "Custom food"

        if not matches:
            calories = explicit_calories or 0.0
            return {
                "name": cleaned_name,
                "brand": "",
                "serving_amount": 1.0,
                "serving_unit": "serving",
                "calories": _round(calories),
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "notes": "No close ingredient match yet, so this fallback kept the macros editable.",
                "assistant_message": (
                    "I could not confidently map that meal to known foods yet. "
                    "If you add rough portions or calories, I can give a better estimate."
                ),
                "confidence": "low",
                "source": "assistant_text",
            }

        totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        notes = []
        for match in matches:
            grams = self._grams_for(match.reference, match.amount, match.unit)
            totals["calories"] += grams * match.reference.calories_per_gram
            totals["protein_g"] += grams * match.reference.protein_per_gram
            totals["carbs_g"] += grams * match.reference.carbs_per_gram
            totals["fat_g"] += grams * match.reference.fat_per_gram
            notes.append(f"{match.amount:g} {match.unit} {match.reference.name.lower()}")

        confidence = "medium"
        assistant_message = f"I estimated this meal as {', '.join(notes)}."
        if explicit_calories is not None and totals["calories"] > 0:
            scale = explicit_calories / totals["calories"]
            totals = {key: value * scale for key, value in totals.items()}
            totals["calories"] = explicit_calories
            confidence = "medium-high"
            assistant_message = (
                f"I matched the meal to {', '.join(notes)} and then scaled the macros to fit {explicit_calories:g} calories."
            )

        return {
            "name": cleaned_name,
            "brand": "",
            "serving_amount": 1.0,
            "serving_unit": "meal",
            "calories": _round(totals["calories"]),
            "protein_g": _round(totals["protein_g"]),
            "carbs_g": _round(totals["carbs_g"]),
            "fat_g": _round(totals["fat_g"]),
            "notes": f"Fallback estimate based on: {', '.join(notes)}.",
            "assistant_message": assistant_message,
            "confidence": confidence,
            "source": "assistant_text",
        }

    def _match_food_references(self, query: str) -> list[MatchedFood]:
        lowered = query.lower()
        occupied_spans: list[tuple[int, int]] = []
        matches: list[MatchedFood] = []

        for alias, reference in self.alias_entries:
            pattern = re.compile(rf"\b{re.escape(alias)}\b", re.I)
            for match in pattern.finditer(lowered):
                span = (match.start(), match.end())
                if any(self._spans_overlap(span, other) for other in occupied_spans):
                    continue
                amount, unit = self._extract_amount_for_alias(lowered, span)
                occupied_spans.append(span)
                matches.append(
                    MatchedFood(
                        reference=reference,
                        alias=alias,
                        start=match.start(),
                        end=match.end(),
                        amount=amount,
                        unit=unit,
                    )
                )
                break

        matches.sort(key=lambda item: item.start)
        return matches

    def _extract_amount_for_alias(self, query: str, span: tuple[int, int]) -> tuple[float, str]:
        window_start = max(0, span[0] - 24)
        window_end = min(len(query), span[1] + 20)
        window = query[window_start:window_end]
        amount_match = None
        for match in AMOUNT_PATTERN.finditer(window):
            global_start = window_start + match.start()
            global_end = window_start + match.end()
            distance = min(abs(global_end - span[0]), abs(global_start - span[1]))
            if distance > 14:
                continue
            amount_match = match
            break

        if amount_match:
            amount = float(amount_match.group("amount"))
            unit = UNIT_ALIASES.get(amount_match.group("unit").lower(), "serving")
            return amount, unit

        count_match = re.search(r"(\d+(?:\.\d+)?)\s*x\b", window)
        if count_match:
            return float(count_match.group(1)), "serving"

        return 1.0, "serving"

    def _clean_food_name(self, query: str) -> str:
        cleaned = CALORIE_PATTERN.sub("", query)
        cleaned = AMOUNT_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"\b(?:with|and|plus)\b", " ", cleaned, flags=re.I)
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

    def _spans_overlap(self, first: tuple[int, int], second: tuple[int, int]) -> bool:
        return first[0] < second[1] and second[0] < first[1]


def _coerce_optional_float(value: Any | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


class NutritionLabelService:
    def __init__(
        self,
        *,
        swift_script_path: str | Path,
        openai_client: OpenAINutritionClient | None = None,
    ):
        self.swift_script_path = Path(swift_script_path)
        self.openai_client = openai_client or OpenAINutritionClient()

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

        if self.openai_client.available:
            try:
                parsed = self.openai_client.parse_label(
                    image_bytes=image_bytes,
                    filename=filename,
                    ocr_text=ocr_text,
                    fallback_name=fallback_name,
                    fallback_brand=fallback_brand,
                )
            except RuntimeError:
                parsed = self.parse_label_text(ocr_text, fallback_name=fallback_name, fallback_brand=fallback_brand)
        else:
            parsed = self.parse_label_text(ocr_text, fallback_name=fallback_name, fallback_brand=fallback_brand)

        parsed["ocr_text"] = ocr_text
        return parsed

    def _extract_text(self, image_path: Path) -> str:
        if not self.swift_script_path.exists():
            raise RuntimeError("The macOS OCR helper script is missing.")

        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError("The uploaded label image could not be read.")

        candidate_paths = [image_path]
        candidate_paths.extend(self._write_preprocessed_variants(image=image, image_path=image_path))

        texts = []
        seen = set()
        for candidate_path in candidate_paths:
            text = self._run_ocr(candidate_path)
            normalized = self._normalize_ocr_text(text)
            if normalized and normalized not in seen:
                seen.add(normalized)
                texts.append(text.strip())

        if not texts:
            raise RuntimeError("No text could be read from that label photo.")
        return "\n\n".join(texts)

    def _write_preprocessed_variants(self, *, image: np.ndarray, image_path: Path) -> list[Path]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enlarged = cv2.resize(gray, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
        denoised = cv2.bilateralFilter(enlarged, 9, 75, 75)
        sharpened = cv2.addWeighted(denoised, 1.5, cv2.GaussianBlur(denoised, (0, 0), 3), -0.5, 0)
        adaptive = cv2.adaptiveThreshold(
            sharpened,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        variants = []
        for name, array in (("gray", sharpened), ("adaptive", adaptive), ("otsu", otsu)):
            variant_path = image_path.with_name(f"{image_path.stem}-{name}.png")
            cv2.imwrite(str(variant_path), array)
            variants.append(variant_path)
        return variants

    def _run_ocr(self, image_path: Path) -> str:
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
        return result.stdout.strip()

    def parse_label_text(
        self,
        text: str,
        *,
        fallback_name: str | None = None,
        fallback_brand: str | None = None,
    ) -> dict[str, Any]:
        lines = self._clean_lines(text)
        if not lines:
            raise RuntimeError("No text could be parsed from that label.")

        normalized_text = "\n".join(lines)
        serving_label = self._extract_serving_size(normalized_text, lines)
        serving_amount, serving_unit = self._parse_serving_amount_unit(serving_label)
        calories = self._extract_calories(normalized_text, lines)
        protein = self._extract_nutrient_value(lines, ["protein"])
        carbs = self._extract_nutrient_value(lines, ["total carbohydrate", "total carbs", "carbohydrate", "carbs"])
        fat = self._extract_nutrient_value(lines, ["total fat", "fat"])

        if calories <= 0 and any(value > 0 for value in (protein, carbs, fat)):
            calories = protein * 4 + carbs * 4 + fat * 9

        display_name = (fallback_name or self._extract_label_title(lines) or "Scanned Item").strip()
        confidence = "medium-high" if calories > 0 and sum(value > 0 for value in (protein, carbs, fat)) >= 2 else "medium"

        return {
            "name": display_name.title(),
            "brand": (fallback_brand or "").strip(),
            "serving_label": serving_label or "1 serving",
            "serving_amount": _round(serving_amount),
            "serving_unit": serving_unit,
            "calories": _round(calories),
            "protein_g": _round(protein),
            "carbs_g": _round(carbs),
            "fat_g": _round(fat),
            "notes": "Parsed from a nutrition label photo with OCR cleanup and fallback nutrition rules.",
            "assistant_message": (
                f"I read the label as {self._format_macro_line(calories, protein, carbs, fat)} "
                f"for {serving_label or '1 serving'}."
            ),
            "confidence": confidence,
            "source": "label_scan",
        }

    def _clean_lines(self, text: str) -> list[str]:
        normalized = self._normalize_ocr_text(text)
        deduped = []
        seen = set()
        for raw_line in normalized.splitlines():
            line = raw_line.strip(" :;|")
            if not line or line in seen:
                continue
            seen.add(line)
            deduped.append(line)
        return deduped

    def _normalize_ocr_text(self, text: str) -> str:
        normalized = text.replace("\r", "\n")
        normalized = normalized.replace("|", " ")
        normalized = normalized.replace("O g", "0 g").replace("Omg", "0 mg")
        normalized = normalized.replace("o g", "0 g").replace("o mg", "0 mg")
        normalized = re.sub(r"(?<=\d)O\b", "0", normalized)
        normalized = re.sub(r"(?<=\bO)(?=\d)", "0", normalized)
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _extract_serving_size(self, text: str, lines: list[str]) -> str:
        match = SERVING_SIZE_PATTERN.search(text)
        if match:
            return match.group(1).strip(" .")
        for index, line in enumerate(lines):
            if "serving size" in line.lower():
                if index + 1 < len(lines) and not re.search(r"\d", line):
                    return lines[index + 1]
                return re.sub(r"(?i)^.*serving size[:\s]*", "", line).strip(" .") or "1 serving"
        return "1 serving"

    def _extract_calories(self, text: str, lines: list[str]) -> float:
        direct_patterns = [
            r"\bcalories\b[:\s]*(\d+(?:\.\d+)?)",
            r"\bcalories from fat\b[:\s]*(\d+(?:\.\d+)?)",
        ]
        for pattern in direct_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return float(match.group(1))

        for index, line in enumerate(lines):
            lowered = line.lower()
            if "calories from fat" in lowered:
                continue
            if "calories" not in lowered:
                continue
            number = self._first_number(line)
            if number is not None:
                return number
            if index + 1 < len(lines):
                number = self._first_number(lines[index + 1])
                if number is not None:
                    return number
        return 0.0

    def _extract_nutrient_value(self, lines: list[str], aliases: list[str]) -> float:
        for index, line in enumerate(lines):
            lowered = line.lower()
            if not any(alias in lowered for alias in aliases):
                continue

            current_line_value = self._grams_from_line(line, aliases)
            if current_line_value is not None:
                return current_line_value

            for look_ahead in range(1, 3):
                if index + look_ahead >= len(lines):
                    break
                next_value = self._grams_from_line(lines[index + look_ahead], aliases)
                if next_value is not None:
                    return next_value
        return 0.0

    def _grams_from_line(self, line: str, aliases: list[str]) -> float | None:
        cleaned = PERCENT_DV_PATTERN.sub("", line)
        nutrient_pattern = "|".join(re.escape(alias) for alias in aliases)
        inline_match = re.search(rf"(?:{nutrient_pattern})[^\d]*(\d+(?:\.\d+)?)\s*g\b", cleaned, re.I)
        if inline_match:
            return float(inline_match.group(1))

        grams_match = re.search(r"(\d+(?:\.\d+)?)\s*g\b", cleaned, re.I)
        if grams_match:
            return float(grams_match.group(1))

        if any(alias in cleaned.lower() for alias in aliases):
            number = self._first_number(cleaned)
            if number is not None:
                return number
        return None

    def _extract_label_title(self, lines: list[str]) -> str:
        for line in lines[:8]:
            lowered = line.lower()
            if any(token in lowered for token in NON_NAME_TOKENS):
                continue
            if len(line) > 80:
                continue
            if sum(character.isdigit() for character in line) > max(2, len(line) // 4):
                continue
            return line
        return ""

    def _parse_serving_amount_unit(self, serving_label: str) -> tuple[float, str]:
        match = AMOUNT_PATTERN.search(serving_label)
        if match:
            return float(match.group("amount")), UNIT_ALIASES.get(match.group("unit").lower(), "serving")
        fallback = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", serving_label)
        if fallback:
            return float(fallback.group(1)), fallback.group(2).lower()
        return 1.0, "serving"

    def _first_number(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1))
        return None

    def _format_macro_line(self, calories: float, protein: float, carbs: float, fat: float) -> str:
        return (
            f"{_round(calories):g} calories, {_round(protein):g}g protein, "
            f"{_round(carbs):g}g carbs, and {_round(fat):g}g fat"
        )


def serialize_estimate(estimate: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(estimate))
