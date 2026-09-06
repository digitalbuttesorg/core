"""Test the Plant Ranger auth helpers and credentials platform."""

from homeassistant.components.plant_ranger.api import SimpleAuth
from homeassistant.components.plant_ranger.application_credentials import (
    async_get_description_placeholders,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


async def test_simple_auth_returns_token(hass: HomeAssistant) -> None:
    """Test the config flow auth hands back the bare token."""
    auth = SimpleAuth(async_get_clientsession(hass), "mock-access-token")

    assert await auth.async_get_access_token() == "mock-access-token"


async def test_description_placeholders(hass: HomeAssistant) -> None:
    """Test the credentials dialog links to the My Home Assistant redirect."""
    placeholders = await async_get_description_placeholders(hass)

    assert placeholders["redirect_url"] == "https://my.home-assistant.io/redirect/oauth"
    assert placeholders["developer_dashboard_url"].startswith("https://")
