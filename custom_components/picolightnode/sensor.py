from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_TARGET_ID, CONF_TARGET_SPACE, SPACE_TC
from .sensor_entity import PicoDimSensor, PicoCctSensor


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    ctx = hass.data[DOMAIN][entry.entry_id]
    coord = ctx["coordinator"]
    device_name = ctx.get("device_name", entry.title)
    device_id = ctx.get("device_id", entry.entry_id)
    targets = ctx["targets"]

    entities = []
    for t in targets:
        tid = t[CONF_TARGET_ID]
        name = t.get("name", tid)
        space = t.get(CONF_TARGET_SPACE, SPACE_TC)

        # DIM sensor - always created
        entities.append(
            PicoDimSensor(
                coordinator=coord,
                entry_id=entry.entry_id,
                device_id=device_id,
                device_name=device_name,
                unique_id=f"{device_id}::{tid}::dim",
                target_id=tid,
                target_name=name,
                name=f"{name} DIM",
            )
        )
        
        # CCT sensor - only for TC targets
        if space == SPACE_TC:
            entities.append(
                PicoCctSensor(
                    coordinator=coord,
                    entry_id=entry.entry_id,
                    device_id=device_id,
                    device_name=device_name,
                    unique_id=f"{device_id}::{tid}::cct",
                    target_id=tid,
                    target_name=name,
                    name=f"{name} CCT",
                )
            )

    async_add_entities(entities)
