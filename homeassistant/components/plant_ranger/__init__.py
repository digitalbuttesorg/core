"""The Plant Ranger integration."""

import logging
from typing import Any

from aiohttp import ClientError
from plantranger import PlantRangerClient

from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
)
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth, async_import_built_in_credential
from .const import CONF_TRACKED_ENTITIES, DOMAIN
from .coordinator import PlantRangerConfigEntry, PlantRangerCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Plant Ranger component."""
    await async_import_built_in_credential(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PlantRangerConfigEntry) -> bool:
    """Set up Plant Ranger from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    auth = AsyncConfigEntryAuth(
        async_get_clientsession(hass), OAuth2Session(hass, entry, implementation)
    )

    try:
        await auth.async_get_access_token()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="auth_failed"
        ) from err
    except (OAuth2TokenRequestError, ClientError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    coordinator = PlantRangerCoordinator(hass, entry, PlantRangerClient(auth))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    tracked_entities = entry.data.get(CONF_TRACKED_ENTITIES, [])
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    @callback
    def handle_sensor_update(event: Event[EventStateChangedData]) -> None:
        """Handle sensor state changes and forward to Plant Ranger."""
        new_state = event.data["new_state"]
        old_state = event.data["old_state"]

        if new_state is None:
            return

        entity_id = new_state.entity_id

        # Only process tracked entities
        if entity_id not in tracked_entities:
            return

        # Skip if state hasn't actually changed
        if old_state and old_state.state == new_state.state:
            return

        # Skip unavailable/unknown states
        if new_state.state in ("unavailable", "unknown"):
            return

        # Extract sensor data with device info
        sensor_data = _extract_sensor_data(
            hass, entity_id, new_state, entity_reg, device_reg
        )

        if sensor_data.get("mac_address"):
            _LOGGER.debug(
                "Sensor update for %s (MAC: %s): %s",
                entity_id,
                sensor_data["mac_address"],
                sensor_data["state"],
            )
        else:
            _LOGGER.debug("Sensor update for %s: %s", entity_id, sensor_data)

    # Subscribe to state changes
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, handle_sensor_update)
    )

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PlantRangerConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _extract_sensor_data(
    hass: HomeAssistant,
    entity_id: str,
    state: State,
    entity_reg: er.EntityRegistry,
    device_reg: dr.DeviceRegistry,
) -> dict[str, Any]:
    """Extract relevant sensor data from state object."""
    data: dict[str, Any] = {
        "entity_id": entity_id,
        "state": state.state,
        "unit_of_measurement": state.attributes.get("unit_of_measurement"),
        "device_class": state.attributes.get("device_class"),
        "friendly_name": state.attributes.get("friendly_name"),
        "timestamp": state.last_updated.isoformat(),
    }

    # Get MAC address from device registry
    entity_entry = entity_reg.async_get(entity_id)
    if entity_entry and entity_entry.device_id:
        device = device_reg.async_get(entity_entry.device_id)
        if isinstance(device, dr.DeviceEntry):
            # Try to extract MAC address from device connections
            mac_address = _get_mac_from_device(device)
            if mac_address:
                data["mac_address"] = mac_address

            # Add additional device metadata
            data["device_manufacturer"] = device.manufacturer
            data["device_model"] = device.model
            data["device_name"] = device.name_by_user or device.name

    return data


def _get_mac_from_device(device: dr.DeviceEntry) -> str | None:
    """Extract MAC address from device connections."""
    # Check for Bluetooth connection (most common for plant sensors)
    for connection_type, connection_id in device.connections:
        if connection_type == CONNECTION_BLUETOOTH:
            return connection_id
        if connection_type == CONNECTION_NETWORK_MAC:
            return connection_id

    return None


async def async_unload_entry(
    hass: HomeAssistant, entry: PlantRangerConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
