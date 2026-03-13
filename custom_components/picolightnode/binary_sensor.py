from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_DEVICE_ID, CONF_TARGET_ID
from .binary_sensor_entity import PicoManualOverrideActive, PicoAutomationOverrideActive


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    ctx = hass.data[DOMAIN][entry.entry_id]
    coord = ctx["coordinator"]
    device_name = ctx.get("device_name", entry.title)
    device_id = entry.data.get(CONF_DEVICE_ID, entry.entry_id)
    targets = ctx["targets"]

    entities = []
    for t in targets:
        tid = t[CONF_TARGET_ID]
        tname = t.get("name", tid)

        entities.append(
            PicoManualOverrideActive(
                coordinator=coord,
                entry_id=entry.entry_id,
                device_id=device_id,
                device_name=device_name,
                target_id=tid,
                target_name=tname,
                unique_id=f"{device_id}::{tid}::manual_override_active",
                name=f"{tname} – Manual Override aktiv",
            )
        )
        entities.append(
            PicoAutomationOverrideActive(
                coordinator=coord,
                entry_id=entry.entry_id,
                device_id=device_id,
                device_name=device_name,
                target_id=tid,
                target_name=tname,
                unique_id=f"{device_id}::{tid}::automation_override_active",
                name=f"{tname} – Automation Override aktiv",
            )
        )

    async_add_entities(entities)
