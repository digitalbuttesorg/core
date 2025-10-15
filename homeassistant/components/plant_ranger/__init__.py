"""The Plant Ranger integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, EVENT_STATE_CHANGED, Platform
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENABLE_DEMO,
    CONF_TRACKED_ENTITIES,
    DOMAIN,
)
from .types import PlantRangerConfigEntry

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class PlantRangerData:
    """Runtime data for Plant Ranger integration."""

    def __init__(self, oauth_session: OAuth2Session) -> None:
        """Initialize the Plant Ranger data."""
        self.oauth_session = oauth_session
        # TODO: Initialize actual API client with OAuth token
        # self.client = PlantRangerClient(oauth_session)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Plant Ranger component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PlantRangerConfigEntry) -> bool:
    """Set up Plant Ranger from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session = OAuth2Session(hass, entry, implementation)

    # Ensure token is valid
    await oauth_session.async_ensure_token_valid()

    tracked_entities = entry.data.get(CONF_TRACKED_ENTITIES, [])
    enable_demo = entry.data.get(CONF_ENABLE_DEMO, False)

    # Initialize runtime data with OAuth session
    runtime_data = PlantRangerData(oauth_session)
    entry.runtime_data = runtime_data

    # Get registries for device/entity lookups
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    _LOGGER.info(
        "Setting up Plant Ranger integration, tracking %d entities (demo mode: %s)",
        len(tracked_entities),
        enable_demo,
    )

    # Set up demo sensor platform if enabled
    if enable_demo:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

    @callback
    def handle_sensor_update(event: Event) -> None:
        """Handle sensor state changes and forward to Plant Ranger."""
        new_state: State | None = event.data.get("new_state")
        old_state: State | None = event.data.get("old_state")

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

        # TODO: Send to Plant Ranger API asynchronously
        # hass.async_create_task(runtime_data.client.send_sensor_data(sensor_data))

    # Subscribe to state changes
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, handle_sensor_update)
    )

    return True


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
        if device:
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
    _LOGGER.info("Unloading Plant Ranger integration")

    # Unload sensor platform if demo mode was enabled
    if entry.data.get(CONF_ENABLE_DEMO, False):
        return await hass.config_entries.async_unload_platforms(
            entry, [Platform.SENSOR]
        )

    return True
