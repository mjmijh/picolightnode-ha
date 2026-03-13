"""Light platform setup for PICOlightnode v2.0.0."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .light_entity import PicoLight


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light entities from config entry."""
    ctx = hass.data[DOMAIN][entry.entry_id]
    coordinator = ctx["coordinator"]
    mqttc = ctx["mqtt"]
    
    # Get targets from options (preferred) or data (fallback)
    targets = entry.options.get("targets") or entry.data.get("targets", [])
    
    lights = [
        PicoLight(
            coordinator,
            mqttc,
            entry.entry_id,
            entry.data.get("device_id", "unknown"),
            entry.data.get("name", "PICO"),
            target,
        )
        for target in targets
    ]
    
    async_add_entities(lights)
