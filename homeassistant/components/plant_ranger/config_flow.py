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
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DEVICE_ID, CONF_MAC, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import SimpleAuth, async_import_built_in_credential
from .const import CONF_ENABLE_DEMO, DEFAULT_TITLE, DOMAIN, SUBENTRY_TYPE_PLANT
from .helpers import async_get_bthome_plant_devices

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

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_PLANT: PlantSubentryFlowHandler}

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


class PlantSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a BTHome plant sensor as a subentry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the user pick a BTHome plant sensor."""
        added_macs = {
            subentry.unique_id for subentry in self._get_entry().subentries.values()
        }
        # DeviceSelector can't exclude devices, so offer only the ones not yet added.
        devices = {
            device.id: (device.name_by_user or device.name or mac, mac)
            for mac, device in async_get_bthome_plant_devices(self.hass).items()
            if mac not in added_macs
        }
        if user_input is not None:
            # It may have been added, disabled or removed since the form was shown.
            if (selected := devices.get(user_input[CONF_DEVICE_ID])) is None:
                return self.async_abort(reason="device_unavailable")
            name, mac = selected
            return self.async_create_entry(
                title=name,
                data={CONF_DEVICE_ID: user_input[CONF_DEVICE_ID], CONF_MAC: mac},
                unique_id=mac,
            )

        if not devices:
            return self.async_abort(reason="no_devices")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=device_id, label=name)
                                for device_id, (name, _) in devices.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    )
                }
            ),
        )
