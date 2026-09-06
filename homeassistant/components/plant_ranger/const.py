"""Constants for the Plant Ranger integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "plant_ranger"

CONF_TRACKED_ENTITIES: Final = "tracked_entities"
CONF_ENABLE_DEMO: Final = "enable_demo"

DEFAULT_TITLE: Final = "Plant Ranger"

# Public OAuth client registered with Plant Ranger for Home Assistant. It carries no
# secret; the authorization code flow is protected with PKCE instead.
OAUTH2_CLIENT_ID: Final = "home_assistant"

SCAN_INTERVAL: Final = timedelta(minutes=10)

MANUFACTURER: Final = "Plant Ranger"

DEMO_PLANT_ID: Final = "demo-plant"
DEMO_PLANT_NAME: Final = "Demo Monstera"
DEMO_MAC_ADDRESS: Final = "AA:BB:CC:DD:EE:FF"
