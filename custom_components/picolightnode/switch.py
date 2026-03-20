from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_TARGET_ID,
    CONF_MANUAL_OVERRIDE_TOPIC,
    CONF_AUTOMATION_OVERRIDE_TOPIC,
    CONF_OVERRIDE_TOPIC,
)
from .switch_entity import PicoFollowExternalSwitch


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    ctx = hass.data[DOMAIN][entry.entry_id]
    coord = ctx["coordinator"]
    mqttc = ctx["mqtt"]
    device_name = ctx.get("device_name", entry.title)
    device_id = ctx.get("device_id", entry.entry_id)
    targets = ctx["targets"]

    entities = []
    for t in targets:
        target_id = t[CONF_TARGET_ID]
        manual_topic = t.get(CONF_MANUAL_OVERRIDE_TOPIC) or t.get(CONF_OVERRIDE_TOPIC)
        auto_topic = t.get(CONF_AUTOMATION_OVERRIDE_TOPIC) or t.get(CONF_OVERRIDE_TOPIC)

        entities.append(
            PicoFollowExternalSwitch(
                coordinator=coord,
                mqttc=mqttc,
                entry_id=entry.entry_id,
                device_id=device_id,
                device_name=device_name,
                name=f"{t.get('name', target_id)} – Sync external automation",
                unique_id=f"{device_id}::{target_id}::follow_external",
                target_id=target_id,
                target_name=t.get('name', target_id),
                manual_override_topic=manual_topic,
                automation_override_topic=auto_topic,
            )
        )

    async_add_entities(entities)
