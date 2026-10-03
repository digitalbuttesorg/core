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
    SUBENTRY_TYPE_PLANT,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry, SubentryFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)

from .conftest import OTHER_TEAM_ID, TEAM_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URI = "https://example.com/auth/external/callback"

MOISTURE_MAC = "A4:C1:38:00:00:01"
OTHER_MOISTURE_MAC = "A4:C1:38:00:00:02"
TEMPERATURE_MAC = "A4:C1:38:00:00:03"
XIAOMI_MAC = "A4:C1:38:00:00:04"


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


def _add_sensor_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    *,
    domain: str,
    mac: str | None,
    name: str,
    device_class: SensorDeviceClass,
) -> dr.DeviceEntry:
    """Register a device with one sensor entity for an integration."""
    entry = MockConfigEntry(domain=domain, unique_id=mac or name)
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, mac)} if mac else set(),
        identifiers={("bluetooth", mac)} if mac else {(domain, name)},
        name=name,
    )
    entity_registry.async_get_or_create(
        "sensor",
        domain,
        f"{mac or name}-{device_class}",
        config_entry=entry,
        device_id=device.id,
        original_device_class=device_class,
    )
    return device


def _add_bthome_moisture_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    *,
    mac: str | None,
    name: str,
) -> dr.DeviceEntry:
    """Register a BTHome device with a soil moisture sensor."""
    return _add_sensor_device(
        hass,
        device_registry,
        entity_registry,
        domain="bthome",
        mac=mac,
        name=name,
        device_class=SensorDeviceClass.MOISTURE,
    )


async def _start_plant_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> SubentryFlowResult:
    """Start the flow that adds a plant subentry."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLANT),
        context={"source": SOURCE_USER},
    )


def _add_plant_subentry(
    hass: HomeAssistant, entry: MockConfigEntry, device: dr.DeviceEntry, mac: str
) -> None:
    """Link a device to a plant as the subentry flow would."""
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data={CONF_DEVICE_ID: device.id, CONF_MAC: mac},
            subentry_type=SUBENTRY_TYPE_PLANT,
            title=device.name or mac,
            unique_id=mac,
        ),
    )


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


async def test_subentry_add_plant(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only BTHome moisture sensors are offered and one can be added."""
    mock_config_entry.add_to_hass(hass)
    basil = _add_bthome_moisture_device(
        hass, device_registry, entity_registry, mac=MOISTURE_MAC, name="Basil sensor"
    )
    aloe = _add_bthome_moisture_device(
        hass,
        device_registry,
        entity_registry,
        mac=OTHER_MOISTURE_MAC,
        name="Aloe sensor",
    )
    _add_sensor_device(
        hass,
        device_registry,
        entity_registry,
        domain="bthome",
        mac=TEMPERATURE_MAC,
        name="Thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
    )
    _add_sensor_device(
        hass,
        device_registry,
        entity_registry,
        domain="xiaomi_ble",
        mac=XIAOMI_MAC,
        name="Flower care",
        device_class=SensorDeviceClass.MOISTURE,
    )

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    config = result["data_schema"].schema[CONF_DEVICE_ID].config
    assert config["sort"] is True
    assert {option["value"]: option["label"] for option in config["options"]} == {
        aloe.id: "Aloe sensor",
        basil.id: "Basil sensor",
    }

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: basil.id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Basil sensor"
    assert result["data"] == {CONF_DEVICE_ID: basil.id, CONF_MAC: MOISTURE_MAC}
    assert result["unique_id"] == MOISTURE_MAC

    (subentry,) = mock_config_entry.subentries.values()
    assert subentry.subentry_type == SUBENTRY_TYPE_PLANT
    assert subentry.unique_id == MOISTURE_MAC


async def test_subentry_user_renamed_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the name the user gave the device is offered and used as the title."""
    mock_config_entry.add_to_hass(hass)
    device = _add_bthome_moisture_device(
        hass,
        device_registry,
        entity_registry,
        mac=MOISTURE_MAC,
        name="BTHome sensor 0001",
    )
    device_registry.async_update_device(device.id, name_by_user="Basil")

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["data_schema"].schema[CONF_DEVICE_ID].config["options"] == [
        {"value": device.id, "label": "Basil"}
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: device.id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Basil"


async def test_subentry_already_added_device_excluded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test devices that already have a plant subentry are not offered."""
    mock_config_entry.add_to_hass(hass)
    added = _add_bthome_moisture_device(
        hass, device_registry, entity_registry, mac=MOISTURE_MAC, name="Basil sensor"
    )
    other = _add_bthome_moisture_device(
        hass,
        device_registry,
        entity_registry,
        mac=OTHER_MOISTURE_MAC,
        name="Aloe sensor",
    )
    _add_plant_subentry(hass, mock_config_entry, added, MOISTURE_MAC)

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema[CONF_DEVICE_ID].config["options"] == [
        {"value": other.id, "label": "Aloe sensor"}
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: other.id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["unique_id"] == OTHER_MOISTURE_MAC
    assert len(mock_config_entry.subentries) == 2


async def test_subentry_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the flow aborts when there are no BTHome plant sensors."""
    mock_config_entry.add_to_hass(hass)
    _add_sensor_device(
        hass,
        device_registry,
        entity_registry,
        domain="bthome",
        mac=TEMPERATURE_MAC,
        name="Thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
    )

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


async def test_subentry_all_devices_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the flow aborts when every BTHome plant sensor is already added."""
    mock_config_entry.add_to_hass(hass)
    device = _add_bthome_moisture_device(
        hass, device_registry, entity_registry, mac=MOISTURE_MAC, name="Basil sensor"
    )
    _add_plant_subentry(hass, mock_config_entry, device, MOISTURE_MAC)

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


async def test_subentry_device_unavailable_on_submit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the flow aborts if the picked sensor was added while the form was open."""
    mock_config_entry.add_to_hass(hass)
    basil = _add_bthome_moisture_device(
        hass, device_registry, entity_registry, mac=MOISTURE_MAC, name="Basil sensor"
    )
    _add_bthome_moisture_device(
        hass,
        device_registry,
        entity_registry,
        mac=OTHER_MOISTURE_MAC,
        name="Aloe sensor",
    )

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM

    # Another "Add plant" dialog finishes first with the same sensor.
    _add_plant_subentry(hass, mock_config_entry, basil, MOISTURE_MAC)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: basil.id}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_unavailable"
    assert len(mock_config_entry.subentries) == 1


async def test_subentry_device_class_overridden_to_moisture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a sensor the user changed to the moisture device class is offered."""
    mock_config_entry.add_to_hass(hass)
    device = _add_sensor_device(
        hass,
        device_registry,
        entity_registry,
        domain="bthome",
        mac=MOISTURE_MAC,
        name="Basil sensor",
        device_class=SensorDeviceClass.HUMIDITY,
    )
    (entity,) = er.async_entries_for_device(entity_registry, device.id)
    entity_registry.async_update_entity(
        entity.entity_id, device_class=SensorDeviceClass.MOISTURE
    )

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema[CONF_DEVICE_ID].config["options"] == [
        {"value": device.id, "label": "Basil sensor"}
    ]


async def test_subentry_device_class_overridden_from_moisture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a moisture sensor the user changed to another device class is not offered."""
    mock_config_entry.add_to_hass(hass)
    device = _add_bthome_moisture_device(
        hass, device_registry, entity_registry, mac=MOISTURE_MAC, name="Basil sensor"
    )
    (entity,) = er.async_entries_for_device(entity_registry, device.id)
    entity_registry.async_update_entity(
        entity.entity_id, device_class=SensorDeviceClass.HUMIDITY
    )

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


async def test_subentry_device_without_bluetooth_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test BTHome plant sensors without a Bluetooth connection are not offered."""
    mock_config_entry.add_to_hass(hass)
    _add_bthome_moisture_device(
        hass, device_registry, entity_registry, mac=None, name="Sensor without MAC"
    )

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


async def test_subentry_disabled_device_excluded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test BTHome plant sensors the user disabled are not offered."""
    mock_config_entry.add_to_hass(hass)
    device = _add_bthome_moisture_device(
        hass, device_registry, entity_registry, mac=MOISTURE_MAC, name="Basil sensor"
    )
    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )

    result = await _start_plant_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"
