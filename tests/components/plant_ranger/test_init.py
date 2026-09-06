"""Test the Plant Ranger integration setup."""

import logging
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from plantranger import (
    OAUTH2_TOKEN,
    PlantRangerAuthError,
    PlantRangerConnectionError,
    Team,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.plant_ranger.const import (
    CONF_TRACKED_ENTITIES,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

TRACKED_ENTITY_ID = "sensor.monstera_soil"


@pytest.mark.usefixtures("mock_client")
async def test_load_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_client")
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test one device per plant and per bridge."""
    await setup_integration(hass, mock_config_entry)

    for device_id in ("plant-1", "plant-2", "bridge-1"):
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, device_id), mock_config_entry.entry_id
        )
        assert device == snapshot(name=device_id)


async def test_auth_failed_on_poll(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Test a rejected token starts reauth."""
    mock_client.get_teams.side_effect = PlantRangerAuthError
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_not_ready_on_poll(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Test an unreachable API retries without starting reauth."""
    mock_client.get_teams.side_effect = PlantRangerConnectionError
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(hass.config_entries.flow.async_progress()) == 0


@pytest.mark.usefixtures("mock_client")
@pytest.mark.parametrize("expires_at", [1])
@pytest.mark.parametrize(
    ("status", "expected_state", "expected_flows"),
    [
        pytest.param(401, ConfigEntryState.SETUP_ERROR, 1, id="reauth"),
        pytest.param(500, ConfigEntryState.SETUP_RETRY, 0, id="retry"),
    ],
)
async def test_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    expected_state: ConfigEntryState,
    expected_flows: int,
) -> None:
    """Test token refresh failures map to reauth or retry."""
    aioclient_mock.post(OAUTH2_TOKEN, status=status)
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
    assert len(hass.config_entries.flow.async_progress()) == expected_flows


async def test_stale_device_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    team: Team,
) -> None:
    """Test a plant that disappears from the account loses its device."""
    await setup_integration(hass, mock_config_entry)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "plant-2"), mock_config_entry.entry_id
    )

    mock_client.get_team.return_value = Team(
        id=team.id, plants=team.plants[:1], bridges=team.bridges
    )
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "plant-2"), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "plant-1"), mock_config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_client")
async def test_tracked_entity_updates_are_logged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test tracked sensor changes are picked up with their device's MAC."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRACKED_ENTITIES: [
                TRACKED_ENTITY_ID,
                "sensor.no_device",
                "sensor.wired",
                "sensor.no_mac",
            ],
        },
    )
    other_entry = MockConfigEntry(domain="bthome", entry_id="bthome-entry")
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:01")},
        manufacturer="b-parasite",
        model="v2",
        name="Monstera sensor",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "bthome",
        "moisture-1",
        suggested_object_id="monstera_soil",
        device_id=device.id,
        config_entry=other_entry,
    )
    wired = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "10:20:30:40:50:60")},
        name="Wired sensor",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "bthome",
        "wired-1",
        suggested_object_id="wired",
        device_id=wired.id,
        config_entry=other_entry,
    )
    no_mac = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("bthome", "no-mac")},
        name="Sensor without MAC",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "bthome",
        "no-mac-1",
        suggested_object_id="no_mac",
        device_id=no_mac.id,
        config_entry=other_entry,
    )
    await setup_integration(hass, mock_config_entry)

    caplog.set_level(logging.DEBUG, logger="homeassistant.components.plant_ranger")
    hass.states.async_set(TRACKED_ENTITY_ID, "40", {"unit_of_measurement": "%"})
    hass.states.async_set("sensor.no_device", "1")
    hass.states.async_set("sensor.wired", "2")
    hass.states.async_set("sensor.no_mac", "3")
    hass.states.async_set("sensor.untracked", "1")
    await hass.async_block_till_done()

    assert (
        f"Sensor update for {TRACKED_ENTITY_ID} (MAC: aa:bb:cc:dd:ee:01): 40"
        in caplog.text
    )
    assert "Sensor update for sensor.wired (MAC: 10:20:30:40:50:60): 2" in caplog.text
    assert "Sensor update for sensor.no_device: " in caplog.text
    assert "Sensor update for sensor.no_mac: " in caplog.text
    assert "sensor.untracked" not in caplog.text

    # Unchanged (attribute-only), unavailable and unknown states are ignored
    caplog.clear()
    hass.states.async_set(TRACKED_ENTITY_ID, "40", {"unit_of_measurement": "%", "x": 1})
    hass.states.async_set(TRACKED_ENTITY_ID, STATE_UNAVAILABLE)
    hass.states.async_set(TRACKED_ENTITY_ID, STATE_UNKNOWN)
    await hass.async_block_till_done()

    assert "Sensor update" not in caplog.text
