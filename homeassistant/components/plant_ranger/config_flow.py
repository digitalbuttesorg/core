"""Config flow for the Plant Ranger integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from plantranger import PlantRangerAuthError, PlantRangerClient, PlantRangerError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import BooleanSelector

from .api import SimpleAuth, async_import_built_in_credential
from .const import CONF_ENABLE_DEMO, DEFAULT_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {vol.Required(CONF_ENABLE_DEMO, default=False): BooleanSelector()}
)


class PlantRangerFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Plant Ranger."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return PlantRangerOptionsFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        await async_import_built_in_credential(self.hass)
        return await super().async_step_user(user_input)

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
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user(user_input)

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update an existing one."""
        client = PlantRangerClient(
            SimpleAuth(
                async_get_clientsession(self.hass), data[CONF_TOKEN][CONF_ACCESS_TOKEN]
            )
        )
        try:
            teams = await client.get_teams()
        except PlantRangerAuthError:
            return self.async_abort(reason="invalid_auth")
        except PlantRangerError:
            return self.async_abort(reason="cannot_connect")

        # Plant Ranger authorizes one team per token and echoes its id with the token.
        team_id = data[CONF_TOKEN].get("team_id")
        team = next((team for team in teams if team.id == team_id), None)
        if team is None and len(teams) == 1:
            team = teams[0]
        if team is None:
            return self.async_abort(reason="no_team")

        await self.async_set_unique_id(team.id)

        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            entry = (
                self._get_reauth_entry()
                if self.source == SOURCE_REAUTH
                else self._get_reconfigure_entry()
            )
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(entry, data_updates=data)

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=team.name or DEFAULT_TITLE, data=data)


class PlantRangerOptionsFlowHandler(OptionsFlow):
    """Handle Plant Ranger options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
