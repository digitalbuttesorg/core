"""Binary sensor platform for the Plant Ranger integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from plantranger import BridgeSummary, PlantSummary

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PlantRangerConfigEntry
from .entity import PlantRangerBridgeEntity, PlantRangerPlantEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PlantRangerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Plant Ranger plant binary sensor."""

    value_fn: Callable[[PlantSummary], bool]


@dataclass(frozen=True, kw_only=True)
class PlantRangerBridgeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Plant Ranger bridge binary sensor."""

    value_fn: Callable[[BridgeSummary], bool]


PLANT_BINARY_SENSORS: tuple[PlantRangerBinarySensorEntityDescription, ...] = (
    PlantRangerBinarySensorEntityDescription(
        key="needs_water",
        translation_key="needs_water",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda plant: plant.needs_water,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="out_of_range",
        translation_key="out_of_range",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda plant: plant.out_of_range,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="moisture_alert",
        translation_key="moisture_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda plant: plant.moisture_alert,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="temperature_alert",
        translation_key="temperature_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda plant: plant.temperature_alert,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="humidity_alert",
        translation_key="humidity_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda plant: plant.humidity_alert,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="light_alert",
        translation_key="light_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda plant: plant.light_alert,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="conductivity_alert",
        translation_key="conductivity_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda plant: plant.conductivity_alert,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="rssi_alert",
        translation_key="rssi_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: plant.rssi_alert,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: plant.low_battery,
    ),
    PlantRangerBinarySensorEntityDescription(
        key="connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plant: not plant.offline,
    ),
)

BRIDGE_BINARY_SENSORS: tuple[PlantRangerBridgeBinarySensorEntityDescription, ...] = (
    PlantRangerBridgeBinarySensorEntityDescription(
        key="connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda bridge: not bridge.offline,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantRangerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plant Ranger binary sensors."""
    coordinator = entry.runtime_data
    known_plants: set[str] = set()
    known_bridges: set[str] = set()

    @callback
    def _check_devices() -> None:
        if new_plants := set(coordinator.data) - known_plants:
            known_plants.update(new_plants)
            async_add_entities(
                PlantRangerBinarySensor(coordinator, plant_id, description)
                for plant_id in new_plants
                for description in PLANT_BINARY_SENSORS
            )
        if new_bridges := set(coordinator.bridges) - known_bridges:
            known_bridges.update(new_bridges)
            async_add_entities(
                PlantRangerBridgeBinarySensor(coordinator, bridge_id, description)
                for bridge_id in new_bridges
                for description in BRIDGE_BINARY_SENSORS
            )

    _check_devices()
    entry.async_on_unload(coordinator.async_add_listener(_check_devices))


class PlantRangerBinarySensor(PlantRangerPlantEntity, BinarySensorEntity):
    """An alert Plant Ranger raises for a plant."""

    entity_description: PlantRangerBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return the current state of the alert."""
        return self.entity_description.value_fn(self.plant)


class PlantRangerBridgeBinarySensor(PlantRangerBridgeEntity, BinarySensorEntity):
    """The state of a Plant Ranger bridge."""

    entity_description: PlantRangerBridgeBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return the current state of the bridge."""
        return self.entity_description.value_fn(self.bridge)
