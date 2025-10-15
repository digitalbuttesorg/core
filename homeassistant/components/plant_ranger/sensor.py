"""Demo sensor platform for Plant Ranger integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import random

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfIlluminance, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_ENABLE_DEMO, DEMO_MAC_ADDRESS, DEMO_PLANT_NAME, DOMAIN
from .types import PlantRangerConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=10)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlantRangerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plant Ranger demo sensors."""
    if not entry.data.get(CONF_ENABLE_DEMO, False):
        return

    _LOGGER.info("Setting up Plant Ranger demo sensors")

    # Create demo device
    device_info = DeviceInfo(
        identifiers={(DOMAIN, DEMO_MAC_ADDRESS)},
        name=DEMO_PLANT_NAME,
        manufacturer="Plant Ranger",
        model="Demo Plant v1.0",
        connections={("bluetooth", DEMO_MAC_ADDRESS)},
    )

    # Create demo sensors
    sensors = [
        PlantRangerDemoSensor(
            device_info=device_info,
            name="Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit=UnitOfTemperature.CELSIUS,
            base_value=22.0,
            variance=3.0,
        ),
        PlantRangerDemoSensor(
            device_info=device_info,
            name="Humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            unit=PERCENTAGE,
            base_value=65.0,
            variance=10.0,
        ),
        PlantRangerDemoSensor(
            device_info=device_info,
            name="Moisture",
            device_class=SensorDeviceClass.MOISTURE,
            unit=PERCENTAGE,
            base_value=45.0,
            variance=5.0,
        ),
        PlantRangerDemoSensor(
            device_info=device_info,
            name="Illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            unit=UnitOfIlluminance.LUX,
            base_value=500.0,
            variance=200.0,
        ),
    ]

    async_add_entities(sensors)

    # Schedule periodic updates
    @callback
    def update_sensors(_now) -> None:
        """Update all demo sensors."""
        for sensor in sensors:
            sensor.update_value()

    entry.async_on_unload(
        async_track_time_interval(hass, update_sensors, UPDATE_INTERVAL)
    )


class PlantRangerDemoSensor(SensorEntity):
    """Demo sensor entity for Plant Ranger."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        device_info: DeviceInfo,
        name: str,
        device_class: SensorDeviceClass,
        unit: str,
        base_value: float,
        variance: float,
    ) -> None:
        """Initialize the demo sensor."""
        self._attr_device_info = device_info
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{DEMO_MAC_ADDRESS}_{device_class}".lower()

        self._base_value = base_value
        self._variance = variance
        self._attr_native_value = base_value

    @callback
    def update_value(self) -> None:
        """Update the sensor value with random variance."""
        # Generate realistic-looking random value
        change = random.uniform(-self._variance / 2, self._variance / 2)
        new_value = self._base_value + change

        # Clamp percentage values
        if self._attr_native_unit_of_measurement == PERCENTAGE:
            new_value = max(0, min(100, new_value))

        self._attr_native_value = round(new_value, 1)
        self.async_write_ha_state()
        _LOGGER.debug(
            "Updated demo sensor %s to %s %s",
            self.name,
            self._attr_native_value,
            self._attr_native_unit_of_measurement,
        )
