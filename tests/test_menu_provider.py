from menu_provider import PlaywrightDiningProvider


def test_parse_periods_response_handles_nested_payload():
    provider = PlaywrightDiningProvider()
    payload = {
        "data": {
            "periods": [
                {"id": "breakfast-id", "name": "Breakfast"},
                {"id": "lunch-id", "name": "Lunch"},
            ]
        }
    }

    periods = provider._parse_periods_response(payload)

    assert periods == [
        {"id": "breakfast-id", "name": "Breakfast"},
        {"id": "lunch-id", "name": "Lunch"},
    ]


def test_parse_menu_payload_normalizes_missing_nutrients_and_duplicate_names():
    provider = PlaywrightDiningProvider()
    payload = {
        "menu": {
            "periods": {
                "categories": [
                    {
                        "name": "Grill",
                        "items": [
                            {
                                "name": "Turkey Sausage",
                                "portion": "2 links",
                                "calories": "160",
                                "nutrients": [
                                    {"name": "Protein", "value": "11"},
                                    {"name": "Total Fat", "value": "12"},
                                ],
                                "allergens": ["Soy"],
                            }
                        ],
                    },
                    {
                        "name": "Bakery",
                        "items": [
                            {
                                "name": "Turkey Sausage",
                                "portion": "1 pastry",
                                "calories": "220",
                                "ingredients": "Flour, Butter",
                            }
                        ],
                    },
                ]
            }
        }
    }

    items = provider._parse_menu_payload(payload, "Islander Dining Hall", "2026-03-26", "Breakfast")

    assert len(items) == 2
    assert items[0]["protein_g"] == 11
    assert items[0]["fat_g"] == 12
    assert items[1]["carbs_g"] == 0
    assert items[0]["id"] != items[1]["id"]
    assert items[1]["ingredients"] == ["Flour", "Butter"]


def test_parse_dialog_text_extracts_macros_and_ingredients():
    provider = PlaywrightDiningProvider()
    text = """
    RASPBERRY BANANA SMOOTHIE
    1 serving per container
    Serving size: 1-1/2 cup
    Calories
    270
    Protein (g)
    10 g
    Total Carbohydrates (g)
    49 g
    Total Fat (g)
    4.5 g
    Ingredients: Soy Milk, Banana, Yogurt
    Close
    """.strip()

    parsed = provider._parse_dialog_text(text)

    assert parsed["portion"] == "1-1/2 cup"
    assert parsed["calories"] == 270
    assert parsed["protein_g"] == 10
    assert parsed["carbs_g"] == 49
    assert parsed["fat_g"] == 4.5
    assert parsed["ingredients"] == ["Soy Milk", "Banana", "Yogurt"]


def test_period_name_from_text_handles_labels_with_extra_hours():
    provider = PlaywrightDiningProvider()

    assert provider._period_name_from_text("Breakfast 7:00 AM - 10:30 AM") == "Breakfast"
    assert provider._period_name_from_text("Lunch served until 2:00 PM") == "Lunch"
    assert provider._period_name_from_text("Dinner (5 PM - 8 PM)") == "Dinner"
    assert provider._period_name_from_text("Something else entirely") is None
