# PICOlightnode v2.0.19

Home Assistant custom integration for PICO lighting hardware controlled via MQTT. The PICO device manages DALI lighting and exposes its targets over MQTT.

- [README (Deutsch)](README.de.md)
- [README (Espanol)](README.es.md)

---

## Requirements

- Home Assistant 2024.1.0 or later
- PICO hardware with MQTT

---

## Installation

**Manual:**

```bash
cd /config
unzip -o picolightnode_v2.0.19.zip
ha core restart
```

**HACS (custom repository):**

Add `https://github.com/mjmijh/picolightnode-ha` as a custom repository in HACS, then install the integration and restart Home Assistant.

---

## Automation Modes

PICOlightnode supports three modes of operation. You can switch between them at any time.

### Mode 1: Manual Control

Direct control via the Home Assistant dashboard.

- No special setup required
- Follow External switch: **OFF**
- Smart Restore remembers brightness and color temperature on the next turn-on

**Best for:** Ad-hoc adjustments, full manual control

---

### Mode 2: Internal Automation (PICO Daily Scheduler)

The PICO device controls itself based on a time-of-day schedule configured in `setup.json`. No Home Assistant automations are needed.

- Follow External switch: **OFF**
- Works even when Home Assistant is offline
- Smart Restore: turning off saves "device" mode — turning on resumes the PICO scheduler

**Best for:** Simple time-based control, standalone operation

---

### Mode 3: External Automation (Follow External)

An external automation (e.g. Keyframe Scheduler) controls the light. PICOlightnode tracks commands from the automation and detects manual overrides.

- Follow External switch: **ON**
- When a manual override is detected, the Follow External switch turns off automatically
- Smart Restore after turn-off from Follow mode: resumes in Manual mode with the saved brightness — Follow mode is intentionally not restored automatically to avoid conflicts with override detection in external automations

**Best for:** Complex schedules, sensor-based adjustments, multi-light synchronisation

---

### Switching Between Modes

| From | To | How |
|------|----|-----|
| Manual | Follow External | Turn Follow External switch **ON** |
| Follow External | Manual | Change brightness in dashboard — Follow disables automatically |
| Follow External | Manual | Turn Follow External switch **OFF** |
| Any | Internal Auto | Press the **Reset All Overrides** button |

---

## Entities

Each configured target creates the following entities:

| Entity | ID pattern | Description |
|--------|------------|-------------|
| Light | `light.<target_name>` | Main light entity — brightness and color temp (TC mode) |
| Switch | `switch.<target_name>_externe_automation_zulassen` | Follow External switch |
| Button | — | Reset manual override |
| Button | — | Reset automation override |
| Button | — | Reset all overrides (returns to Internal Auto mode) |

### Light Entity Attributes

| Attribute | Values | Description |
|-----------|--------|-------------|
| `follow_external_automation` | `true` / `false` | Whether Follow External mode is active |
| `mode_before_off` | `follow` / `device` / `manual` | Mode that was active before the light was turned off |

---

## MQTT Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `<base_topic>/state` | Device → HA | Device publishes current state (brightness, cct) |
| `<base_topic>/override/manual` | HA → Device | Integration sends manual override commands |
| `<base_topic>/override/automation` | HA → Device | Integration sends automation override commands |

---

## PICO setup.json Configuration

The `setup.json` file defines which light targets the PICO creates, how they behave, and where the computed values are sent (DALI bus, MQTT, HTTP).

### DALI Device Types

| Type | Description |
|------|-------------|
| **DT8** | Native Tunable White — single DALI address, CCT sent natively via `DT8TC` |
| **DT6** | Standard DALI — CCT produced by blending two separate DAPC channels (warm white + cool white) |

Use **DT8** when the ballast fully implements DALI Device Type 8. Use **DT6** for all other CCT ballasts.

Example configurations for both types are available in [`docs/examples/setup/`](docs/examples/setup/).

### Structure

A `setup.json` is a JSON array of **Targets**. Each target represents one light channel.

```json
{
  "type"         : "TARGET",
  "space"        : "TC",
  "comment"      : "building/area/room/lightentityCCT",
  "behaviors"    : [...],
  "destinations" : [...]
}
```

**Behaviors** determine the light value. The integration uses two override behaviors per target — one for automation control (`/override/automation`) and one for manual control (`/override/manual`).

**Destinations** determine where the computed value is sent: `DALI` (bus output), `MESSAGING` (MQTT state publication), `HTTPSERVER` (HTTP state query).

---

## Context Tracking

All state changes made internally by the integration carry the Context ID `picolightnode_internal`. This allows external blueprints (e.g. Keyframe Scheduler) to distinguish between user-initiated actions and integration-internal updates, enabling reliable manual override detection.

---

## Related Integrations

| Integration | Repository |
|-------------|------------|
| Keyframe Scheduler | https://github.com/mjmijh/keyframe-scheduler |
| CCT Astronomy | https://github.com/mjmijh/cct-astronomy |

---

## Issues and Support

https://github.com/mjmijh/picolightnode-ha/issues
