"""Test the Plant Ranger sensor platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from plantranger import PlantRangerConnectionError, PlantSummary, Team
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.plant_ranger.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

MOISTURE_ENTITY_ID = "sensor.living_room_monstera_moisture"


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    with patch("homeassistant.components.plant_ranger.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors go unavailable when the API cannot be reached."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(MOISTURE_ENTITY_ID).state == "41.2"

    mock_client.get_teams.side_effect = PlantRangerConnectionError
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(MOISTURE_ENTITY_ID).state == STATE_UNAVAILABLE


async def test_new_plant_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    team: Team,
) -> None:
    """Test a plant added to the account gets entities without a reload."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.pothos_moisture") is None

    new_plant = PlantSummary(id="plant-3", name="Pothos", moisture=60.0)
    mock_client.get_team.return_value = Team(
        id=team.id, plants=[*team.plants, new_plant], bridges=team.bridges
    )
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pothos_moisture").state == "60.0"
