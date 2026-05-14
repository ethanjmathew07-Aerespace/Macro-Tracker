from __future__ import annotations

from dataclasses import dataclass


API_BASE = "https://apiv4.dineoncampus.com"


@dataclass(frozen=True)
class DiningLocationConfig:
    name: str
    menu_page_url: str
    api_location_id: str


ISLANDER_DINING = DiningLocationConfig(
    name="Islander Dining Hall",
    menu_page_url="https://dineoncampus.com/islanderdining/location-menus",
    api_location_id="58824e93ee596febed45b319",
)

DINING_LOCATIONS = {
    ISLANDER_DINING.name: ISLANDER_DINING,
}

DEFAULT_LOCATION_NAME = ISLANDER_DINING.name

PERIODS_URL = "{base}/locations/{unit_id}/periods/?date={date}"
MENU_URL = "{base}/locations/{unit_id}/menu?date={date}&period={period_id}"
