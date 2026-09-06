# Plant Ranger integration plan

Surface a Plant Ranger account's plants in Home Assistant as devices with sensors and
alerts, so automations can be built on plant status, alerts and metrics. Every plant the
account can see becomes a Plant Ranger device, whether its readings arrive through a
BTHome V2 sensor in Home Assistant or through a Plant Ranger bridge.

## Status

| Area | State | Notes |
|---|---|---|
| `plantranger` client library | Done, unpublished | `~/repos/digitalbuttesorg/python-plantranger`, installed editable into `.venv` |
| OAuth config flow, reauth, reconfigure | Done | Built-in public client with PKCE, no user credentials; blocked end to end on server work below |
| Coordinator polling `/v1/teams` + `/v1/teams/{id}` | Done | 10 minute interval, stale device pruning |
| Plant devices, sensors, binary sensors | Done | Modelled on `fyta`, see design notes |
| Bridge devices with connectivity | Done | |
| Demo plant behind an options toggle | Done | Same entity path as a real plant |
| Diagnostics | Done | Tokens and MACs redacted |
| Tests | Done | 21 tests, snapshots in `tests/components/plant_ranger/snapshots` |
| hassfest, gen_requirements_all, prek | Done | Run on 2026-09-05 |
| Publish `plantranger` 0.1.0 to PyPI | Todo | Manifest pins `plantranger==0.1.0` |
| Docs PR (home-assistant.io) | Todo | `quality_scale.yaml` marks the docs rules exempt until then |
| Brands PR (home-assistant/brands) | Assets ready | `~/repos/digitalbuttesorg/brands-plant-ranger/core_integrations/plant_ranger/`; core integrations cannot ship images, the frontend loads them from brands.home-assistant.io |
| State forwarder for tracked entities | Deferred | No ingest endpoint on the API yet |
| Local dev mode | Done | `PLANTRANGER_API_HOST` / `PLANTRANGER_WEB_HOST` env vars, read by the library |

## Server work

Implemented in `~/repos/plant-metrics` on 2026-09-06 (uncommitted):

- `POST https://www.plantranger.com/oauth/token` handles both `authorization_code` and
  `refresh_token`, accepts form-encoded bodies, and sits outside the CSRF pipeline.
- The code exchange returns a 1 hour access token, a rotating 365 day refresh token,
  `expires_in` and `team_id`.
- PKCE (S256) is required for the `home_assistant` client and verified on exchange.
- Redirect URIs are allowlisted per client (`OAUTH_HOME_ASSISTANT_REDIRECT_URIS` on the
  backend, `config :plant_ranger, :oauth_clients` on the frontend).
- Refresh is refused once the linked access token is revoked, so authorization code
  reuse ends the whole chain.

The migration (`oauth_authorization_code_pkce`) is applied to the local dev database.
Still to do: commit and deploy those changes, run the migration in prod, and add an
ingest endpoint before the state forwarder can send anything.

## Design

- OAuth uses a shipped public client id with PKCE, the pattern `teslemetry` and `overkiz`
  use, imported in `async_setup` so the credentials dialog never appears. Users can still
  register their own client under Application credentials. Nabu Casa cloud account
  linking was considered and rejected because it needs a Cloud subscription and a core
  release before it works.
- Client code lives in a separate PyPI package, as `fyta` (`fyta_cli`) and `miele`
  (`pymiele`) do. `api.py` adapts Home Assistant's `OAuth2Session` to the library's
  `AbstractAuth`.
- Tokens are scoped to one team, so there is one config entry per team, keyed on the
  team id the token endpoint returns (falling back to the single team `/v1/teams`
  lists). The coordinator flattens that team's plants into `dict[plant_id, PlantSummary]`.
- Devices are identified by `(plant_ranger, plant_id)` only. Sharing the sensor's
  Bluetooth MAC as a connection used to merge a cloud device onto the local BTHome
  device, but the device registry in this tree scopes identifiers and connections to a
  single config entry, so it would now create a duplicate device instead. Plant Ranger
  plants therefore sit alongside the BTHome device rather than merging with it.
- Entity unique IDs are prefixed with the config entry id because teams can be shared
  between accounts, so the same plant can legitimately appear under two entries.
- The `status` sensor is a plain string rather than an enum: the API's status
  vocabulary is not documented, and an enum sensor raises on any value not in its
  option list.
- Sensors: moisture, temperature, humidity, illuminance, conductivity, battery, signal
  strength, last checkup, status. Binary sensors: needs water, out of range, the six
  per-metric alerts, low battery, connectivity. Measurement sensors go unavailable when
  the plant is offline; alerts and connectivity keep reporting.
- The `EVENT_STATE_CHANGED` forwarder is unchanged and still only logs.

## Verification

```bash
python3 -m script.hassfest --integration-path homeassistant/components/plant_ranger
python3 -m script.gen_requirements_all validate
python3 -m script.translations develop --integration plant_ranger
uv run --no-sync pytest tests/components/plant_ranger
uv run --no-sync prek run --all-files
```

Manual, once the server work is in: add application credentials, complete the flow,
confirm one device per plant, confirm a BTHome plant does not appear twice.
