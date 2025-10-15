"""Constants for the Plant Ranger integration."""

from typing import Final

DOMAIN: Final = "plant_ranger"

# Config flow constants
CONF_API_KEY: Final = "api_key"
CONF_API_URL: Final = "api_url"
CONF_TRACKED_ENTITIES: Final = "tracked_entities"
CONF_ENABLE_DEMO: Final = "enable_demo"

# Default values
DEFAULT_API_URL: Final = "https://api.plantranger.com"

# Demo plant data
DEMO_PLANT_NAME: Final = "Demo Monstera"
DEMO_MAC_ADDRESS: Final = "AA:BB:CC:DD:EE:FF"
