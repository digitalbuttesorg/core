# Plant Ranger

Home Assistant integration for [Plant Ranger](https://www.plantranger.com). It signs in
with OAuth, polls the account's teams every 10 minutes, and turns each plant and bridge
into a device so automations can react to plant status, alerts and readings.

Status and outstanding work are tracked in [PLAN.md](PLAN.md).

## What you get

Per plant:

- Sensors: moisture, temperature, humidity, illuminance, conductivity, battery,
  signal strength (disabled by default), last checkup, status
- Binary sensors: needs water, out of range, moisture/temperature/humidity/light/
  conductivity/signal alerts, low battery, connectivity

Per bridge: a connectivity binary sensor.

Measurement sensors go unavailable while a plant is offline; alerts and connectivity keep
reporting so an "offline" automation still fires. Plants that disappear from the account
have their device removed on the next poll; new plants appear without a reload.

Plant Ranger plants are separate devices from any BTHome device for the same sensor. The
device registry no longer merges devices across integrations, so they sit side by side.

## Run it locally

```bash
cd ~/repos/digitalbuttesorg/core
source .venv/bin/activate
hass -c config --debug
```

Sign in with the owner user created when this `config/` was first onboarded. There is
no default password; reset it with `hass --script auth -c config change_password <user>`
while Home Assistant is stopped.

Then in http://localhost:8123: Settings → Devices & services → Add integration →
Plant Ranger → log in to Plant Ranger and approve. The integration ships a public OAuth
client (`OAUTH2_CLIENT_ID` in `const.py`) secured with PKCE, so no client ID or secret is
needed; the first time, my.home-assistant.io asks for your instance URL
(`http://localhost:8123`). Anyone who wants their own OAuth app can still add it under
Settings → Application credentials.

Debug logging, under `logger:` in `config/configuration.yaml`:

```yaml
logger:
  logs:
    homeassistant.components.plant_ranger: debug
    plantranger: debug
```

Each config entry covers one Plant Ranger team and takes the team's name. Once signed
in, **Configure** on the entry offers a demo plant with changing readings for building
automations without hardware.

To test against a local Plant Ranger stack, set these before `hass` (they are read by the
`plantranger` library, so the integration needs no changes):

```bash
export PLANTRANGER_API_HOST=http://localhost:8084   # REST API
export PLANTRANGER_WEB_HOST=http://localhost:4000   # OAuth authorize and token endpoints
hass -c config --debug
```

The local server still needs the `home_assistant` client registered with redirect URI
`https://my.home-assistant.io/redirect/oauth`; the redirect back to `http://localhost:8123`
works because my.home-assistant.io only forwards to the instance URL stored in your
browser.

## Tests and checks

```bash
uv run --no-sync pytest tests/components/plant_ranger
python3 -m script.hassfest --integration-path homeassistant/components/plant_ranger
uv run --no-sync prek run --all-files
```

The tests mock the API client, so they need no server.

## Layout

| File | Role |
|---|---|
| `api.py` | Adapts Home Assistant's `OAuth2Session` to the library's `AbstractAuth` |
| `application_credentials.py` | Authorize and token URLs for the credentials flow |
| `config_flow.py` | OAuth flow, reauth, reconfigure, options (demo toggle) |
| `coordinator.py` | Polling, plant/bridge maps, stale device removal, demo plant |
| `entity.py` | Base plant and bridge entities and their `DeviceInfo` |
| `sensor.py`, `binary_sensor.py` | Entity descriptions and platform setup |
| `diagnostics.py` | Config entry diagnostics, tokens and MACs redacted |

The API client is the separate `plantranger` package
(`~/repos/digitalbuttesorg/python-plantranger`), pinned in `manifest.json`. Integrations
in core must keep protocol code in a published PyPI library, so it needs publishing before
this can be merged.
