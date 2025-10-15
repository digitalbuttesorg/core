"""Constants for the Plant Ranger integration."""

from typing import Final

DOMAIN: Final = "plant_ranger"

# OAuth2 endpoints
OAUTH2_AUTHORIZE: Final = "https://api.plantranger.com/oauth/authorize"
OAUTH2_TOKEN: Final = "https://api.plantranger.com/oauth/token"

# Config flow constants
CONF_TRACKED_ENTITIES: Final = "tracked_entities"
CONF_ENABLE_DEMO: Final = "enable_demo"

# Default values
DEFAULT_API_URL: Final = "https://api.plantranger.com"
DEFAULT_TITLE: Final = "Plant Ranger"

# Demo plant data
DEMO_PLANT_NAME: Final = "Demo Monstera"
DEMO_MAC_ADDRESS: Final = "AA:BB:CC:DD:EE:FF"
