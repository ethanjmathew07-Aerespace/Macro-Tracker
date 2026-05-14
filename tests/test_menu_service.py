from dining_config import ISLANDER_DINING
from menu_provider import MenuDocument, MenuProvider, MenuSyncError
from menu_service import MenuSyncService
from storage import SQLiteRepository


class SuccessfulProvider(MenuProvider):
    def fetch_menu(self, location, date):
        assert location == ISLANDER_DINING
        return MenuDocument(
            location=location.name,
            date=date,
            status="fresh",
            fetched_at="2026-03-26T08:30:00-05:00",
            periods={
                "Breakfast": [
                    {
                        "id": "eggs-breakfast",
                        "location": location.name,
                        "date": date,
                        "period": "Breakfast",
                        "station": "Grill",
                        "name": "Scrambled Eggs",
                        "serving_label": "1 serving",
                        "calories": 180,
                        "protein_g": 12,
                        "carbs_g": 2,
                        "fat_g": 13,
                        "ingredients": ["Eggs"],
                        "allergens": ["Egg"],
                        "source_hash": "eggs-breakfast",
                    }
                ]
            },
        )


class FailingProvider(MenuProvider):
    def fetch_menu(self, location, date):
        raise MenuSyncError("Cloudflare blocked the sync.")


def test_menu_service_returns_stale_snapshot_when_refresh_fails(tmp_path):
    repository = SQLiteRepository(db_path=tmp_path / "tracker.db", legacy_json_path=tmp_path / "macros.json")
    repository.initialize()

    success_service = MenuSyncService(repository, SuccessfulProvider())
    fresh_payload = success_service.get_menu(date="2026-03-26")
    assert fresh_payload["status"] == "fresh"

    failing_service = MenuSyncService(repository, FailingProvider())
    stale_payload = failing_service.get_menu(date="2026-03-26")

    assert stale_payload["status"] == "stale"
    assert "cached menu" in stale_payload["warning"].lower()
    assert stale_payload["periods"]["Breakfast"][0]["name"] == "Scrambled Eggs"

