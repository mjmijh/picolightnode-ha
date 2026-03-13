"""Button platform setup for PICOlightnode v2.0.0."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .button_entity import (
    PicoResetManualOverrideButton,
    PicoResetAutomationOverrideButton,
    PicoResetAllOverridesButton,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from config entry."""
    ctx = hass.data[DOMAIN][entry.entry_id]
    device_name = ctx.get("device_name", entry.title)
    device_id = ctx.get("device_id", entry.entry_id)
    targets = ctx["targets"]

    entities = []
    for t in targets:
        # Create 3 buttons per target
        entities.append(
            PicoResetManualOverrideButton(
                hass, entry, entry.entry_id, device_id, device_name, t
            )
        )
        entities.append(
            PicoResetAutomationOverrideButton(
                hass, entry, entry.entry_id, device_id, device_name, t
            )
        )
        entities.append(
            PicoResetAllOverridesButton(
                hass, entry, entry.entry_id, device_id, device_name, t
            )
        )

    async_add_entities(entities)
