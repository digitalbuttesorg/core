"""API for Plant Ranger bound to Home Assistant OAuth."""

from typing import cast, override

from aiohttp import ClientSession
from plantranger import API_HOST, AbstractAuth

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_TITLE, DOMAIN, OAUTH2_CLIENT_ID


async def async_import_built_in_credential(hass: HomeAssistant) -> None:
    """Register the shipped public OAuth client so users need no credentials of their own.

    Called from both the component setup and the config flow, because the component is
    not set up until a config entry exists.
    """
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(OAUTH2_CLIENT_ID, "", name=DEFAULT_TITLE)
    )


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Plant Ranger authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Plant Ranger auth."""
        super().__init__(websession, API_HOST)
        self._oauth_session = oauth_session

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token["access_token"])


class SimpleAuth(AbstractAuth):
    """Provide Plant Ranger authentication before a config entry exists."""

    def __init__(self, websession: ClientSession, access_token: str) -> None:
        """Initialize Plant Ranger auth."""
        super().__init__(websession, API_HOST)
        self._access_token = access_token

    @override
    async def async_get_access_token(self) -> str:
        """Return the access token."""
        return self._access_token
