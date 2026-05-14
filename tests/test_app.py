from app import create_app


def build_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": tmp_path / "tracker.db",
            "LEGACY_JSON_PATH": tmp_path / "macros.json",
        }
    )


def build_client(tmp_path):
    return build_app(tmp_path).test_client()


def test_primary_routes_render(tmp_path):
    client = build_client(tmp_path)

    assert client.get("/").status_code == 200
    assert client.get("/assistant").status_code == 200
    assert client.get("/library").status_code == 200
    assert client.get("/fast-food").status_code == 200
    assert client.get("/settings").status_code == 200
    assert client.get("/dining").status_code in {301, 302}


def test_dashboard_and_burn_update(tmp_path):
    client = build_client(tmp_path)

    create_response = client.post(
        "/api/meals",
        json={
            "date": "2026-05-14",
            "name": "Greek Yogurt",
            "protein_g": 17,
            "carbs_g": 8,
            "fat_g": 0,
            "calories": 100,
        },
    )
    assert create_response.status_code == 201

    burn_response = client.post(
        "/api/day/burn",
        json={"date": "2026-05-14", "calories_burned": 2650},
    )
    assert burn_response.status_code == 200
    dashboard = burn_response.get_json()["dashboard"]
    assert dashboard["day"]["calories_burned"] == 2650
    assert dashboard["day"]["deficit"] == 2550


def test_assistant_estimate_endpoint(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/assistant/estimate",
        json={"query": "200g chicken breast 330 calories"},
    )
    assert response.status_code == 200
    estimate = response.get_json()["estimate"]
    assert estimate["name"] == "Chicken Breast"
    assert estimate["calories"] == 330
    assert estimate["protein_g"] > 50


def test_library_item_can_be_created_and_logged(tmp_path):
    client = build_client(tmp_path)

    create_response = client.post(
        "/api/library-items",
        json={
            "name": "Fairlife Protein Shake",
            "brand": "Fairlife",
            "serving_amount": 1,
            "serving_unit": "bottle",
            "calories": 150,
            "protein_g": 30,
            "carbs_g": 4,
            "fat_g": 2,
            "source": "label_scan",
        },
    )
    assert create_response.status_code == 201
    item_id = create_response.get_json()["library_item"]["id"]

    log_response = client.post(
        f"/api/library-items/{item_id}/log",
        json={"date": "2026-05-14", "servings": 2},
    )
    assert log_response.status_code == 201
    payload = log_response.get_json()
    assert payload["meal"]["source"] == "library_item"
    assert payload["meal"]["protein_g"] == 60
    assert payload["dashboard"]["day"]["totals"]["calories"] == 300


def test_saved_meal_can_be_created_logged_and_deleted(tmp_path):
    client = build_client(tmp_path)

    create_response = client.post(
        "/api/saved-meals",
        json={
            "name": "Protein Bar",
            "protein_g": 20,
            "carbs_g": 24,
            "fat_g": 7,
            "calories": 230,
        },
    )
    assert create_response.status_code == 201
    saved_meal_id = create_response.get_json()["saved_meal"]["id"]

    log_response = client.post(
        f"/api/saved-meals/{saved_meal_id}/log",
        json={"date": "2026-05-14", "servings": 2},
    )
    assert log_response.status_code == 201
    assert log_response.get_json()["meal"]["calories"] == 460

    delete_response = client.delete(f"/api/saved-meals/{saved_meal_id}")
    assert delete_response.status_code == 200


def test_fast_food_catalog_and_log(tmp_path):
    client = build_client(tmp_path)

    catalog_response = client.get("/api/fast-food")
    assert catalog_response.status_code == 200
    restaurants = catalog_response.get_json()["restaurants"]
    assert any(restaurant["slug"] == "chick-fil-a" for restaurant in restaurants)

    log_response = client.post(
        "/api/fast-food/log",
        json={
            "date": "2026-05-14",
            "item_id": "popeyes-classic-chicken-sandwich",
            "servings": 1.5,
        },
    )
    assert log_response.status_code == 201
    payload = log_response.get_json()
    assert payload["meal"]["source"] == "fast_food"
    assert payload["meal"]["calories"] == 1050


def test_settings_update_supports_calorie_and_burn_goals(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/settings",
        json={
            "daily_calorie_goal": 2400,
            "daily_protein_goal": 200,
            "daily_carbs_goal": 250,
            "daily_fat_goal": 70,
            "default_calories_burned": 2900,
        },
    )
    assert response.status_code == 200
    settings = response.get_json()["settings"]
    assert settings["daily_calorie_goal"] == 2400
    assert settings["default_calories_burned"] == 2900
