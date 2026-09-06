"""Sensor platform for the Plant Ranger integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from plantranger import PlantSummary

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfConductivity,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import PlantRangerConfigEntry
from .entity import PlantRangerPlantEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PlantRangerSensorEntityDescription(SensorEntityDescription):
    """Describes a Plant Ranger sensor."""

    value_fn: Callable[[PlantSummary], StateType | datetime]


SENSORS: tuple[PlantRangerSensorEntityDescription, ...] = (
    PlantRangerSensorEntityDescription(
        key="moisture",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plant: plant.moisture,
    ),
    PlantRangerSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plant: plant.temperature,
    ),
    PlantRangerSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plant: plant.humidity,
    ),
    PlantRangerSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plant: plant.light,
    ),
    PlantRangerSensorEntityDescription(
        key="conductivity",
        device_class=SensorDeviceClass.CONDUCTIVITY,
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plant: plant.conductivity,
    ),
    PlantRangerSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: plant.battery,
    ),
    PlantRangerSensorEntityDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda plant: plant.signal_strength,
    ),
    PlantRangerSensorEntityDescription(
        key="last_checkup",
        translation_key="last_checkup",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: plant.last_checkup,
    ),
    PlantRangerSensorEntityDescription(
        key="status",
        translation_key="status",
        value_fn=lambda plant: plant.status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantRangerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plant Ranger sensors."""
    coordinator = entry.runtime_data
    known_plants: set[str] = set()

    @callback
    def _check_plants() -> None:
        if new_plants := set(coordinator.data) - known_plants:
            known_plants.update(new_plants)
            async_add_entities(
                PlantRangerSensor(coordinator, plant_id, description)
                for plant_id in new_plants
                for description in SENSORS
            )

    _check_plants()
    entry.async_on_unload(coordinator.async_add_listener(_check_plants))


class PlantRangerSensor(PlantRangerPlantEntity, SensorEntity):
    """A measurement reported by Plant Ranger for a plant."""

    entity_description: PlantRangerSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the current reading."""
        return self.entity_description.value_fn(self.plant)

    @property
    @override
    def available(self) -> bool:
        """Readings go stale once the sensor stops reporting."""
        return super().available and not self.plant.offline
