from storage import SQLiteRepository


def test_legacy_json_import_runs_once(tmp_path):
    legacy_path = tmp_path / "macros.json"
    legacy_path.write_text(
        """
        {
          "macros": {
            "2026-03-25": [
              {
                "meal": "Imported oats",
                "protein": 12,
                "carbs": 48,
                "fat": 8,
                "calories": 320,
                "timestamp": "2026-03-25T08:00:00"
              }
            ]
          },
          "settings": {
            "daily_protein_goal": 180,
            "daily_carbs_goal": 220,
            "daily_fat_goal": 70
          }
        }
        """.strip()
    )

    db_path = tmp_path / "tracker.db"
    repository = SQLiteRepository(db_path=db_path, legacy_json_path=legacy_path)
    repository.initialize()

    settings = repository.get_settings()
    day = repository.get_day("2026-03-25")

    assert settings["daily_protein_goal"] == 180
    assert len(day["meals"]) == 1
    assert day["totals"]["calories"] == 320

    repository_again = SQLiteRepository(db_path=db_path, legacy_json_path=legacy_path)
    repository_again.initialize()
    day_again = repository_again.get_day("2026-03-25")

    assert len(day_again["meals"]) == 1

