"""Config flow for Plant Ranger integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PlantRangerFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Plant Ranger."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        # TODO: Extract user ID from token response
        # user_id = str(data[CONF_TOKEN]["user_id"])
        # await self.async_set_unique_id(user_id)
        # self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data=data,
        )
