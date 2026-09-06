"""Test the Plant Ranger integration setup."""

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

from homeassistant.components.plant_ranger.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


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
