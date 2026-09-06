"""Diagnostics support for Plant Ranger."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import PlantRangerConfigEntry

TO_REDACT = {"access_token", "refresh_token", "mac_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PlantRangerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "plants": [asdict(plant) for plant in coordinator.data.values()],
            "bridges": [asdict(bridge) for bridge in coordinator.bridges.values()],
        },
        TO_REDACT,
    )
