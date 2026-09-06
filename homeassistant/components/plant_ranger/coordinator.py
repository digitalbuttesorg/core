"""Coordinator for the Plant Ranger integration."""

import logging
import random
from typing import override

from plantranger import (
    BridgeSummary,
    PlantRangerAuthError,
    PlantRangerClient,
    PlantRangerError,
    PlantSummary,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_DEMO,
    DEMO_MAC_ADDRESS,
    DEMO_PLANT_ID,
    DEMO_PLANT_NAME,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type PlantRangerConfigEntry = ConfigEntry[PlantRangerCoordinator]


class PlantRangerCoordinator(DataUpdateCoordinator[dict[str, PlantSummary]]):
    """Poll every team the account can see and flatten it to plants by id."""

    config_entry: PlantRangerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PlantRangerConfigEntry,
        client: PlantRangerClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Plant Ranger",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.bridges: dict[str, BridgeSummary] = {}
        self._known_devices: set[str] = set()

    @override
    async def _async_update_data(self) -> dict[str, PlantSummary]:
        """Fetch the current plant and bridge summaries."""
        try:
            teams = await self.client.get_teams()
            details = [await self.client.get_team(team.id) for team in teams]
        except PlantRangerAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except PlantRangerError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        plants = {plant.id: plant for team in details for plant in team.plants}
        self.bridges = {
            bridge.id: bridge for team in details for bridge in team.bridges
        }

        if self.config_entry.options.get(CONF_ENABLE_DEMO):
            plants[DEMO_PLANT_ID] = _demo_plant()

        self._async_remove_stale_devices(set(plants) | set(self.bridges))
        return plants

    def _async_remove_stale_devices(self, current: set[str]) -> None:
        """Drop devices for plants and bridges the account no longer has."""
        if removed := self._known_devices - current:
            device_registry = dr.async_get(self.hass)
            for device_id in removed:
                if device := device_registry.async_get_device_by_identifier(
                    (DOMAIN, device_id), self.config_entry.entry_id
                ):
                    device_registry.async_remove_device(device.id)
        self._known_devices = current


def _demo_plant() -> PlantSummary:
    """Build a synthetic plant so the integration can be exercised without hardware."""

    def jitter(base: float, variance: float, low: float, high: float) -> float:
        value = base + random.uniform(-variance / 2, variance / 2)
        return round(min(max(value, low), high), 1)

    return PlantSummary(
        id=DEMO_PLANT_ID,
        name=DEMO_PLANT_NAME,
        species="Monstera deliciosa",
        mac_address=DEMO_MAC_ADDRESS,
        status="ok",
        last_checkup=dt_util.utcnow(),
        battery=jitter(85.0, 4.0, 0, 100),
        conductivity=jitter(900.0, 100.0, 0, 5000),
        humidity=jitter(65.0, 10.0, 0, 100),
        light=jitter(500.0, 200.0, 0, 100000),
        moisture=jitter(45.0, 5.0, 0, 100),
        signal_strength=jitter(-62.0, 6.0, -120, 0),
        temperature=jitter(22.0, 3.0, -50, 60),
    )
