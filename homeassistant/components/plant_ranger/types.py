"""Type definitions for Plant Ranger integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from . import PlantRangerData

type PlantRangerConfigEntry = ConfigEntry[PlantRangerData]
