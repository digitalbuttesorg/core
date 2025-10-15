"""Config flow for Plant Ranger integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_API_KEY,
    CONF_API_URL,
    CONF_ENABLE_DEMO,
    CONF_TRACKED_ENTITIES,
    DOMAIN,
)


class PlantRangerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plant Ranger."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # TODO: Validate API key and connection to Plant Ranger service
            # try:
            #     await validate_api_key(user_input[CONF_API_KEY], user_input[CONF_API_URL])
            # except InvalidAuth:
            #     errors["base"] = "invalid_auth"
            # except CannotConnect:
            #     errors["base"] = "cannot_connect"
            # else:
            #     # TODO: Set unique_id based on account ID from API
            #     # await self.async_set_unique_id(account_id)
            #     # self._abort_if_unique_id_configured()

            if not errors:
                return self.async_create_entry(
                    title="Plant Ranger",
                    data=user_input,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_API_URL, default="https://api.plantranger.com"): str,
                vol.Optional(CONF_TRACKED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        device_class=[
                            "temperature",
                            "humidity",
                            "moisture",
                            "illuminance",
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_ENABLE_DEMO, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
