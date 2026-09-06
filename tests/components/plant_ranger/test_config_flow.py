"""Test the Plant Ranger config flow."""

from unittest.mock import AsyncMock

from plantranger import (
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    PlantRangerAuthError,
    PlantRangerConnectionError,
    TeamListItem,
)
import pytest
from yarl import URL

from homeassistant.components.plant_ranger.const import (
    CONF_ENABLE_DEMO,
    DOMAIN,
    OAUTH2_CLIENT_ID,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import OTHER_TEAM_ID, TEAM_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URI = "https://example.com/auth/external/callback"


async def _complete_oauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
    access_token: str = "mock-access-token",
    team_id: str | None = None,
) -> None:
    """Drive the external OAuth step to completion."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": flow_id, "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    token = {
        "refresh_token": "mock-refresh-token",
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 60,
    }
    if team_id is not None:
        token["team_id"] = team_id
    aioclient_mock.post(OAUTH2_TOKEN, json=token)


@pytest.mark.usefixtures("current_request_with_host", "mock_client")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test creating a config entry through the OAuth flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    url = URL(result["url"])
    assert f"{url.origin()}{url.path}" == OAUTH2_AUTHORIZE
    assert url.query["response_type"] == "code"
    assert url.query["client_id"] == OAUTH2_CLIENT_ID
    assert url.query["redirect_uri"] == REDIRECT_URI
    assert url.query["state"] == state
    assert url.query["code_challenge"]
    assert url.query["code_challenge_method"] == "S256"

    await _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result["flow_id"])
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"]["token"]["access_token"] == "mock-access-token"
    assert result["result"].unique_id == TEAM_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_team_from_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: AsyncMock,
) -> None:
    """Test the team id returned with the token picks the entry's team."""
    mock_client.get_teams.return_value = [
        TeamListItem(id=TEAM_ID, name="Home"),
        TeamListItem(id=OTHER_TEAM_ID, name="Greenhouse"),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _complete_oauth(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        team_id=OTHER_TEAM_ID,
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Greenhouse"
    assert result["result"].unique_id == OTHER_TEAM_ID


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_team(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: AsyncMock,
) -> None:
    """Test aborting when the token grants no team."""
    mock_client.get_teams.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result["flow_id"])
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_team"


@pytest.mark.usefixtures("current_request_with_host", "mock_client")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the team is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result["flow_id"])
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        pytest.param(PlantRangerAuthError, "invalid_auth", id="auth_error"),
        pytest.param(PlantRangerConnectionError, "cannot_connect", id="connection"),
    ],
)
async def test_team_lookup_fails(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_client: AsyncMock,
    side_effect: type[Exception],
    expected_reason: str,
) -> None:
    """Test aborting when the team cannot be looked up after OAuth."""
    mock_client.get_teams.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await _complete_oauth(hass, hass_client_no_auth, aioclient_mock, result["flow_id"])
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("team_id", "expected_reason", "expected_setup_calls", "expected_token"),
    [
        pytest.param(
            TEAM_ID, "reauth_successful", 1, "updated-access-token", id="success"
        ),
        pytest.param(
            OTHER_TEAM_ID, "wrong_account", 0, "mock-access-token", id="wrong_account"
        ),
    ],
)
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    team_id: str,
    expected_reason: str,
    expected_setup_calls: int,
    expected_token: str,
) -> None:
    """Test reauthentication flow outcomes."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_teams.return_value = [TeamListItem(id=team_id, name="Home")]

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _complete_oauth(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        access_token="updated-access-token",
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert mock_setup_entry.await_count == expected_setup_calls
    assert mock_config_entry.data["token"]["access_token"] == expected_token


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("team_id", "expected_reason", "expected_setup_calls", "expected_token"),
    [
        pytest.param(
            TEAM_ID, "reconfigure_successful", 1, "updated-access-token", id="success"
        ),
        pytest.param(
            OTHER_TEAM_ID, "wrong_account", 0, "mock-access-token", id="wrong_account"
        ),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    team_id: str,
    expected_reason: str,
    expected_setup_calls: int,
    expected_token: str,
) -> None:
    """Test reconfiguration flow outcomes."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_teams.return_value = [TeamListItem(id=team_id, name="Home")]

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"

    await _complete_oauth(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        access_token="updated-access-token",
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert mock_setup_entry.await_count == expected_setup_calls
    assert mock_config_entry.data["token"]["access_token"] == expected_token


@pytest.mark.usefixtures("mock_client")
async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test toggling the demo plant through the options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ENABLE_DEMO: True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_ENABLE_DEMO: True}
    assert hass.states.get("sensor.demo_monstera_moisture") is not None
