"""Button entities for PICOlightnode v2.0.3."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base_entity import PicoTargetDeviceInfoMixin
from .const import (
    CONF_MANUAL_OVERRIDE_TOPIC,
    CONF_OVERRIDE_TOPIC,
    CONF_TARGET_SPACE,
    DOMAIN,
    SPACE_TC,
)
from .coordinator import PicoCoordinator
from .models import PicoTargetState
from .mqtt_client import PicoMqtt
from .services import merge_point, publish_override_point

_LOGGER = logging.getLogger(__name__)


class _BasePicoTargetButton(
    CoordinatorEntity[PicoCoordinator],
    PicoTargetDeviceInfoMixin,
    ButtonEntity,
):
    """Base class for PICO target buttons."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        entry_id: str,
        device_id: str,
        device_name: str,
        target: dict,
    ) -> None:
        """Initialize button."""
        ctx = hass.data[DOMAIN][entry.entry_id]
        coordinator: PicoCoordinator = ctx["coordinator"]
        
        CoordinatorEntity.__init__(self, coordinator)
        
        # Set mixin attributes (no __init__ call needed)
        self._device_id = device_id
        self._device_name = device_name
        self._target_id = target["id"]
        self._target_name = target.get("name", self._target_id)
        
        self.hass = hass
        self._entry = entry
        self._target = target


class PicoResetManualOverrideButton(_BasePicoTargetButton):
    """Button to reset manual override.
    
    Sets manual_override.enabled = false
    PICO will:
    - If automation_override=true → Continue with external automation
    - If automation_override=false → Use internal automation
    """
    
    _attr_icon = "mdi:hand-back-left-off"

    def __init__(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry, 
        entry_id: str, 
        device_id: str, 
        device_name: str, 
        target: dict
    ) -> None:
        """Initialize reset manual override button."""
        super().__init__(hass, entry, entry_id, device_id, device_name, target)
        self._attr_unique_id = f"{entry_id}::{self._target_id}::reset_manual"
        self._attr_name = f"{target.get('name', self._target_id)} – Manual Override zurücksetzen"

    async def async_press(self) -> None:
        """Handle button press - reset manual override."""
        ctx = self.hass.data[DOMAIN][self._entry.entry_id]
        mqttc = ctx["mqtt"]
        coord = ctx["coordinator"]

        st = coord.data.get(self._target_id)
        manual_topic = (
            self._target.get(CONF_MANUAL_OVERRIDE_TOPIC) 
            or self._target.get(CONF_OVERRIDE_TOPIC)
        )
        
        if not manual_topic or not st:
            _LOGGER.warning(
                "Cannot reset manual override: missing topic or state (tid=%s)", 
                self._target_id
            )
            return

        # Get current values for smooth transition
        space = self._target.get(CONF_TARGET_SPACE, SPACE_TC)
        point = merge_point(st, brightness_255=None, temperature_k=None, fade_s=3.0, space=space)
        
        # Reset manual override (enabled=False)
        await publish_override_point(mqttc, manual_topic, point, enabled=False, space=space)
        
        # Update local state
        st.manual_override_enabled = False
        
        _LOGGER.info(f"Reset manual override for {self._target_id}")


class PicoResetAutomationOverrideButton(_BasePicoTargetButton):
    """Button to reset automation override.
    
    Sets automation_override.enabled = false
    Disables Follow External automation
    PICO will:
    - If manual_override=true → Continue with manual control
    - If manual_override=false → Use internal automation
    """
    
    _attr_icon = "mdi:auto-mode"

    def __init__(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry, 
        entry_id: str, 
        device_id: str, 
        device_name: str, 
        target: dict
    ) -> None:
        """Initialize reset automation override button."""
        super().__init__(hass, entry, entry_id, device_id, device_name, target)
        self._attr_unique_id = f"{entry_id}::{self._target_id}::reset_automation"
        self._attr_name = f"{target.get('name', self._target_id)} – Automation Override zurücksetzen"

    async def async_press(self) -> None:
        """Handle button press - reset automation override."""
        ctx = self.hass.data[DOMAIN][self._entry.entry_id]
        mqttc = ctx["mqtt"]
        coord = ctx["coordinator"]

        st = coord.data.get(self._target_id)
        automation_topic = self._target.get(CONF_OVERRIDE_TOPIC)
        
        if not automation_topic or not st:
            _LOGGER.warning(
                "Cannot reset automation override: missing topic or state (tid=%s)", 
                self._target_id
            )
            return

        # Get current values for smooth transition
        space = self._target.get(CONF_TARGET_SPACE, SPACE_TC)
        point = merge_point(st, brightness_255=None, temperature_k=None, fade_s=3.0, space=space)
        
        # Reset automation override (enabled=False)
        await publish_override_point(mqttc, automation_topic, point, enabled=False, space=space)
        
        # Update local state
        st.automation_override_enabled = False
        st.follow_external = False  # Follow External is disabled
        
        # Notify coordinator to update Follow switch
        coord.async_set_updated_data(coord.data)
        
        _LOGGER.info(f"Reset automation override for {self._target_id}")


class PicoResetAllOverridesButton(_BasePicoTargetButton):
    """Button to reset ALL overrides (manual + automation).
    
    Sets both manual_override.enabled = false AND automation_override.enabled = false
    GUARANTEED to activate PICO internal automation
    """
    
    _attr_icon = "mdi:restart"

    def __init__(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry, 
        entry_id: str, 
        device_id: str, 
        device_name: str, 
        target: dict
    ) -> None:
        """Initialize reset all overrides button."""
        super().__init__(hass, entry, entry_id, device_id, device_name, target)
        self._attr_unique_id = f"{entry_id}::{self._target_id}::reset_all"
        self._attr_name = f"{target.get('name', self._target_id)} – Alle Overrides zurücksetzen"

    async def async_press(self) -> None:
        """Handle button press - reset ALL overrides."""
        ctx = self.hass.data[DOMAIN][self._entry.entry_id]
        mqttc = ctx["mqtt"]
        coord = ctx["coordinator"]

        st = coord.data.get(self._target_id)
        manual_topic = (
            self._target.get(CONF_MANUAL_OVERRIDE_TOPIC) 
            or self._target.get(CONF_OVERRIDE_TOPIC)
        )
        automation_topic = self._target.get(CONF_OVERRIDE_TOPIC)
        
        if not st:
            _LOGGER.warning(
                "Cannot reset overrides: missing state (tid=%s)", 
                self._target_id
            )
            return

        # Get current values for smooth transition
        space = self._target.get(CONF_TARGET_SPACE, SPACE_TC)
        point = merge_point(st, brightness_255=None, temperature_k=None, fade_s=3.0, space=space)
        
        # Reset manual override
        if manual_topic:
            await publish_override_point(mqttc, manual_topic, point, enabled=False, space=space)
        
        # Reset automation override (if different topic)
        if automation_topic and automation_topic != manual_topic:
            await publish_override_point(mqttc, automation_topic, point, enabled=False, space=space)
        
        # Update local state
        st.manual_override_enabled = False
        st.automation_override_enabled = False
        st.follow_external = False
        
        # Notify coordinator to update Follow switch
        coord.async_set_updated_data(coord.data)
        
        _LOGGER.info(f"Reset ALL overrides for {self._target_id} - Internal Auto active")
