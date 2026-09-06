"""Fixtures for the Plant Ranger integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from plantranger import Team, TeamListItem
import pytest

from homeassistant.components.plant_ranger.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

TEAM_ID = "team-1"
OTHER_TEAM_ID = "team-2"
OWNER_ID = "account-1"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up application credentials; the flow registers the built-in client itself."""
    assert await async_setup_component(hass, "application_credentials", {})


@pytest.fixture
def expires_at() -> int:
    """Return a token expiry in the future."""
    return 9_999_999_999


@pytest.fixture
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Return a Plant Ranger config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEAM_ID,
        title="Home",
        entry_id="01J0000000000000000000PLANT",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "token_type": "Bearer",
            },
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.plant_ranger.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def team() -> Team:
    """Return the team fixture as a library model."""
    return Team.from_dict(load_json_object_fixture("team.json", DOMAIN))


@pytest.fixture
def mock_client(team: Team) -> Generator[AsyncMock]:
    """Mock the Plant Ranger client."""
    with (
        patch(
            "homeassistant.components.plant_ranger.PlantRangerClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.plant_ranger.config_flow.PlantRangerClient",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.get_teams.return_value = [
            TeamListItem(id=TEAM_ID, name="Home", owner_id=OWNER_ID, role="owner")
        ]
        client.get_team.return_value = team
        yield client
