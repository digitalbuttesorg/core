"""Base entities for the Plant Ranger integration."""

from typing import override

from plantranger import BridgeSummary, PlantSummary

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PlantRangerCoordinator


class PlantRangerPlantEntity(CoordinatorEntity[PlantRangerCoordinator]):
    """Base entity for a Plant Ranger plant."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlantRangerCoordinator,
        plant_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._plant_id = plant_id
        self.entity_description = description
        # Teams can be shared, so the same plant may show up under two accounts.
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{plant_id}-{description.key}"
        )

        plant = self.plant
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, plant_id)},
            manufacturer=MANUFACTURER,
            model=plant.species,
            name=plant.name,
            suggested_area=plant.location,
        )

    @property
    def plant(self) -> PlantSummary:
        """Return the current summary for this plant."""
        return self.coordinator.data[self._plant_id]

    @property
    @override
    def available(self) -> bool:
        """Return if the plant is still known to the account."""
        return super().available and self._plant_id in self.coordinator.data


class PlantRangerBridgeEntity(CoordinatorEntity[PlantRangerCoordinator]):
    """Base entity for a Plant Ranger bridge."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlantRangerCoordinator,
        bridge_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._bridge_id = bridge_id
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{bridge_id}-{description.key}"
        )

        bridge = self.bridge
        connections: set[tuple[str, str]] = set()
        if bridge.mac_address:
            connections = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(bridge.mac_address))
            }

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bridge_id)},
            connections=connections,
            manufacturer=MANUFACTURER,
            model=bridge.device_type,
            name=bridge.name,
            suggested_area=bridge.location,
            sw_version=bridge.version,
        )

    @property
    def bridge(self) -> BridgeSummary:
        """Return the current summary for this bridge."""
        return self.coordinator.bridges[self._bridge_id]

    @property
    @override
    def available(self) -> bool:
        """Return if the bridge is still known to the account."""
        return super().available and self._bridge_id in self.coordinator.bridges
