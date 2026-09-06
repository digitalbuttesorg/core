---
title: Plant Ranger
description: Instructions on how to integrate Plant Ranger plants with Home Assistant.
ha_category:
  - Sensor
  - Binary sensor
ha_release: "2026.11"
ha_iot_class: Cloud Polling
ha_config_flow: true
ha_codeowners:
  - "@digitalbuttesorg"
ha_domain: plant_ranger
ha_platforms:
  - binary_sensor
  - sensor
ha_integration_type: service
ha_quality_scale: bronze
---

<!-- Draft for home-assistant/home-assistant.io: source/_integrations/plant_ranger.markdown -->

The **Plant Ranger** {% term integration %} brings the plants monitored by
[Plant Ranger](https://www.plantranger.com) into Home Assistant. Each plant becomes a
device with its latest soil and environment readings and the alerts Plant Ranger raises
for it, so automations can react when a plant needs water or a sensor goes offline.

## Prerequisites

- A Plant Ranger account with at least one team.
- You must be an admin or owner of the team you want to connect.

No client ID or client secret is needed: the integration ships with a registered
Plant Ranger application and signs in with OAuth.

{% include integrations/config_flow.md %}

Home Assistant opens the Plant Ranger website, where you sign in, pick the team, and
approve access. One config entry covers one team; add the integration again for each
additional team.

## Configuration options

{% include integrations/option_flow.md %}

{% configuration_basic %}
Add a demo plant:
  description: Creates a fake plant whose readings change every update, so you can build automations before real sensors report.
{% endconfiguration_basic %}

## Supported functionality

### Sensors

Each plant provides:

- **Moisture** (soil, %)
- **Temperature** (°C)
- **Humidity** (%)
- **Illuminance** (lx)
- **Conductivity** (µS/cm)
- **Battery** (%)
- **Signal strength** (dBm, disabled by default)
- **Last checkup** (timestamp)
- **Status** (Plant Ranger's overall assessment)

### Binary sensors

Each plant provides:

- **Needs water**
- **Out of range**
- **Moisture**, **Temperature**, **Humidity**, **Light**, **Conductivity** and
  **Signal alerts**, mirroring the thresholds configured in Plant Ranger
- **Battery** (low battery)
- **Connectivity**

Each Plant Ranger bridge provides a **Connectivity** binary sensor.

## Data updates

The integration {% term polling polls %} Plant Ranger every 10 minutes. Plants added to
or removed from the team in Plant Ranger appear or disappear on the next update without
reloading the integration.

## Known limitations

- Readings come from Plant Ranger, not directly from the sensor. A plant whose sensor
  also reports to Home Assistant through BTHome appears as two separate devices.
- Measurement sensors become unavailable while Plant Ranger reports the plant offline;
  alert and connectivity binary sensors keep their last state so automations can react.

## Troubleshooting

### Sign-in ends with "Account linking rejected"

Only team admins and owners can authorize integrations. Ask a team owner to grant you
the role, or to add the integration themselves.

### Entities are unavailable

Plant Ranger could not be reached, or the plant's sensor stopped reporting. Check the
plant in Plant Ranger; the integration recovers on its own once data is flowing again.

## Removing the integration

This integration follows standard integration removal.

{% include integrations/remove_device_service.md %}

After removal, revoke Home Assistant's access under your team's settings in Plant
Ranger.
