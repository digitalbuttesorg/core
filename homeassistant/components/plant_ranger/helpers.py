"""Helpers for the Plant Ranger integration."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import BTHOME_DOMAIN


def get_bluetooth_mac(device: dr.DeviceEntry) -> str | None:
    """Return the Bluetooth MAC address of a device."""
    return next(
        (
            connection_id
            for connection_type, connection_id in device.connections
            if connection_type == dr.CONNECTION_BLUETOOTH
        ),
        None,
    )


@callback
def async_get_bthome_plant_devices(hass: HomeAssistant) -> dict[str, dr.DeviceEntry]:
    """Return enabled BTHome devices that have a soil moisture sensor, keyed by MAC."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    devices: dict[str, dr.DeviceEntry] = {}

    for entry in hass.config_entries.async_entries(BTHOME_DOMAIN):
        for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            if (
                entity.domain == Platform.SENSOR
                and entity.device_id is not None
                and (entity.device_class or entity.original_device_class)
                == SensorDeviceClass.MOISTURE
                and (
                    device := dev_reg.async_get(
                        entity.device_id, include_child_devices=False
                    )
                )
                and not device.disabled
                and (mac := get_bluetooth_mac(device))
            ):
                devices[mac] = device

    return devices
