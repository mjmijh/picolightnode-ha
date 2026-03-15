"""Light entity for PICOlightnode - v2.0.18 with Context Tracking."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .base_entity import PicoTargetDeviceInfoMixin
from .const import (
    ATTR_FOLLOW_EXTERNAL,
    ATTR_OVERRIDE_ENABLED,
    ATTR_MANUAL_OVERRIDE_ENABLED,
    ATTR_AUTOMATION_OVERRIDE_ENABLED,
    CONF_MANUAL_OVERRIDE_TOPIC,
    CONF_AUTOMATION_OVERRIDE_TOPIC,
    CONF_OVERRIDE_TOPIC,
    CONF_TARGET_SPACE,
    DOMAIN,
    SPACE_TC,
    SPACE_BRIGHTNESS,
)
from .coordinator import PicoCoordinator
from .models import PicoTargetState
from .mqtt_client import PicoMqtt
from .services import brightness_01_to_ha, merge_point, publish_override_point

_LOGGER = logging.getLogger(__name__)


class PicoLight(
    CoordinatorEntity[PicoCoordinator], 
    PicoTargetDeviceInfoMixin,
    RestoreEntity,
    LightEntity
):
    """Light entity for a PICOlightnode target - v2.0.6.
    
    Full state persistence:
    - Smart turn-on/off state (mode, brightness, temp)
    - Override states (manual, automation, follow)
    - All states survive HA restart and power loss
    
    State synchronization:
    - self._xxx (persistent via RestoreEntity)
    - coordinator.data (runtime for MQTT handlers)
    """

    def __init__(
        self,
        coordinator: PicoCoordinator,
        mqttc: PicoMqtt,
        entry_id: str,
        device_id: str,
        device_name: str,
        target: dict,
    ) -> None:
        """Initialize light entity."""
        super().__init__(coordinator)
        
        # Set PicoTargetDeviceInfoMixin attributes directly
        self._entry_id = entry_id
        self._device_id = device_id
        self._device_name = device_name
        self._target = target
        self._target_id = target["id"]
        self._target_name = target.get("name", self._target_id)
        
        self._mqtt = mqttc
        self._target_space = target.get(CONF_TARGET_SPACE, SPACE_TC)
        
        # Set color mode
        if self._target_space == SPACE_BRIGHTNESS:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
        
        # Topics
        self._manual_override_topic = (
            target.get(CONF_MANUAL_OVERRIDE_TOPIC) or target.get(CONF_OVERRIDE_TOPIC)
        )
        if not self._manual_override_topic:
            raise ValueError(f"manual_override_topic required for {self._target_id}")

        # Entity attributes
        tname = target.get("name", self._target_id)
        self._attr_name = f"{device_name} {tname}"
        self._attr_unique_id = f"{entry_id}::{self._target_id}::light"

        # Kelvin range (TC only)
        if self._target_space == SPACE_TC:
            self._attr_min_color_temp_kelvin = int(target.get("min_kelvin", 2700))
            self._attr_max_color_temp_kelvin = int(target.get("max_kelvin", 5700))
        
        # PERSISTENT STATE - restored from last_state
        # Smart Turn-On/Off
        self._mode_before_off: str | None = None
        self._brightness_before_off: int | None = None
        self._temperature_before_off: int | None = None
        
        # Override States (synced with coordinator.data)
        self._follow_external: bool = False
        self._manual_override_enabled: bool = False
        self._automation_override_enabled: bool = False

    async def async_added_to_hass(self) -> None:
        """Entity added to HA - restore state and reset PICO overrides."""
        await super().async_added_to_hass()
        
        # 1. Restore ALL persistent state
        old_state = await self.async_get_last_state()
        if old_state and old_state.attributes:
            self._mode_before_off = old_state.attributes.get("mode_before_off")
            self._brightness_before_off = old_state.attributes.get("brightness_before_off")
            self._temperature_before_off = old_state.attributes.get("temperature_before_off")
            self._follow_external = old_state.attributes.get(ATTR_FOLLOW_EXTERNAL, False)
            self._manual_override_enabled = old_state.attributes.get(ATTR_MANUAL_OVERRIDE_ENABLED, False)
            self._automation_override_enabled = old_state.attributes.get(ATTR_AUTOMATION_OVERRIDE_ENABLED, False)
            
            _LOGGER.info(
                f"{self.entity_id}: Restored state - mode={self._mode_before_off}, "
                f"b={self._brightness_before_off}, follow={self._follow_external}, "
                f"manual_ovr={self._manual_override_enabled}, auto_ovr={self._automation_override_enabled}"
            )
            
            # 2. Sync restored state to coordinator.data
            st = self._state()
            st.follow_external = self._follow_external
            st.manual_override_enabled = self._manual_override_enabled
            st.automation_override_enabled = self._automation_override_enabled
        
        # 3. Reset ALL PICO overrides → Internal Auto
        await self._reset_pico_overrides()

    async def _reset_pico_overrides(self) -> None:
        """Reset all PICO overrides to disabled (Internal Auto mode)."""
        st = self._state()
        
        # Use current or default brightness
        brightness_01 = 1.0
        if st.point and st.point.brightness_01:
            brightness_01 = st.point.brightness_01
        elif st.last_brightness_01:
            brightness_01 = st.last_brightness_01
        
        # Temperature (TC only)
        temperature_k = None
        if self._target_space == SPACE_TC:
            if st.point and st.point.temperature_k:
                temperature_k = st.point.temperature_k
            elif st.last_temperature_k:
                temperature_k = st.last_temperature_k
        
        point = merge_point(
            st,
            brightness_255=int(brightness_01 * 255),
            temperature_k=temperature_k,
            fade_s=0.0,
            space=self._target_space
        )
        
        # Reset manual override
        if self._manual_override_topic:
            await publish_override_point(
                self._mqtt, self._manual_override_topic, point,
                enabled=False, space=self._target_space
            )
        
        # Reset automation override
        automation_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
        if automation_topic and automation_topic != self._manual_override_topic:
            await publish_override_point(
                self._mqtt, automation_topic, point,
                enabled=False, space=self._target_space
            )
        
        # Update persistent state (follow_external is preserved from RestoreEntity)
        self._manual_override_enabled = False
        self._automation_override_enabled = False

        # Sync to coordinator (follow_external intentionally NOT reset here —
        # it is managed by PicoFollowExternalSwitch via RestoreEntity)
        st.manual_override_enabled = False
        st.automation_override_enabled = False

        _LOGGER.info(f"{self.entity_id}: Reset to Internal Auto mode")

    def _state(self) -> PicoTargetState:
        """Get current target state."""
        if self.coordinator.data is None:
            return PicoTargetState()
        return self.coordinator.data.get(self._target_id, PicoTargetState())

    def _sync_state_to_coordinator(self) -> None:
        """Sync persistent state to coordinator.data."""
        st = self._state()
        st.follow_external = self._follow_external
        st.manual_override_enabled = self._manual_override_enabled
        st.automation_override_enabled = self._automation_override_enabled

    def _sync_state_from_coordinator(self) -> None:
        """Sync coordinator.data to persistent state."""
        st = self._state()
        self._follow_external = st.follow_external
        self._manual_override_enabled = st.manual_override_enabled
        self._automation_override_enabled = st.automation_override_enabled

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        st = self._state()
        
        if st.point is not None:
            b = st.point.brightness_01
        elif st.last_sent_point is not None:
            b = st.last_sent_point.brightness_01
        elif st.last_brightness_01 is not None:
            b = st.last_brightness_01
        else:
            return False
        
        return b > 0.0

    @property
    def brightness(self) -> int | None:
        """Return brightness (0-255)."""
        st = self._state()
        
        if st.point is not None:
            b = st.point.brightness_01
        elif st.last_sent_point is not None:
            b = st.last_sent_point.brightness_01
        elif st.last_brightness_01 is not None:
            b = st.last_brightness_01
        else:
            return None
        
        return brightness_01_to_ha(b)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return color temperature in Kelvin."""
        st = self._state()
        
        if st.point is not None:
            t = st.point.temperature_k
        elif st.last_sent_point is not None:
            t = st.last_sent_point.temperature_k
        elif st.last_temperature_k is not None:
            t = st.last_temperature_k
        else:
            return None
        
        return int(t) if t else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity state attributes (persistent via RestoreEntity)."""
        # Sync from coordinator before returning
        self._sync_state_from_coordinator()
        
        return {
            # Override states (persistent)
            ATTR_FOLLOW_EXTERNAL: self._follow_external,
            ATTR_MANUAL_OVERRIDE_ENABLED: self._manual_override_enabled,
            ATTR_AUTOMATION_OVERRIDE_ENABLED: self._automation_override_enabled,
            # Legacy (from coordinator, may not be accurate)
            ATTR_OVERRIDE_ENABLED: self._state().override_enabled,
            # Smart turn-on/off (persistent)
            "mode_before_off": self._mode_before_off,
            "brightness_before_off": self._brightness_before_off,
            "temperature_before_off": self._temperature_before_off,
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn light on - smart restore or manual control.
        
        Priority:
        1. Smart Restore: If mode_before_off exists, restore that mode (ignore brightness parameter)
        2. Manual Control: Otherwise, apply brightness/temperature from parameters or use saved values
        """
        st = self._state()
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        temp_k = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        transition = kwargs.get(ATTR_TRANSITION)

        _LOGGER.warning(
            f"mode_before_off={self._mode_before_off}, "
            f"brightness kwarg={brightness}"
        )

        # SMART RESTORE has priority over brightness parameter!
        # If we saved a mode before turning off, restore that mode
        if self._mode_before_off:
            _LOGGER.warning(
                f"ignoring brightness parameter"
            )
            await self._restore_mode(st, transition)
            return
        
        # No saved mode - manual control
        await self._manual_control(st, brightness, temp_k, transition)

    async def _restore_mode(self, st: PicoTargetState, transition: float | None) -> None:
        """Restore previous mode after turn-off."""
        mode = self._mode_before_off
        
        if mode == "follow":
            # Follow mode is NOT auto-restored on turn-on.
            # The user must explicitly enable the Follow External switch to resume automation.
            # Reason: auto-restore runs in user context (user_id set), which causes KFS
            # Manual Override Detection to immediately turn off the Follow External switch again.
            # Instead, turn on with saved brightness in manual mode.
            restore_b = self._brightness_before_off or 255
            restore_t = self._temperature_before_off

            point = merge_point(st, restore_b, restore_t, 3.0, self._target_space)
            st.last_sent_point = point
            st.point = point  # Immediate UI update

            await publish_override_point(
                self._mqtt, self._manual_override_topic, point,
                enabled=True, space=self._target_space
            )

            self._manual_override_enabled = True
            st.manual_override_enabled = True

            _LOGGER.info(
                f"{self.entity_id}: Turned on (was follow mode) - manual control "
                f"(b={restore_b}, t={restore_t}). Enable Follow External switch to resume automation."
            )
            
        elif mode == "device":
            # Release all overrides → Internal Auto
            # PICO's internal automation will control brightness/temp
            
            # Release manual (no point needed)
            await publish_override_point(
                self._mqtt, self._manual_override_topic, point=None,
                enabled=False, space=self._target_space
            )
            
            # Release automation (no point needed)
            automation_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
            if automation_topic and automation_topic != self._manual_override_topic:
                await publish_override_point(
                    self._mqtt, automation_topic, point=None,
                    enabled=False, space=self._target_space
                )
            
            self._manual_override_enabled = False
            self._automation_override_enabled = False
            self._follow_external = False
            self._sync_state_to_coordinator()
            
            # Don't set st.point - wait for PICO to send its internal automation state
            
            _LOGGER.info(f"{self.entity_id}: Restored Internal Auto mode (PICO controls)")
        
        elif mode == "manual":
            # Restore manual control
            restore_b = self._brightness_before_off or 255
            restore_t = self._temperature_before_off
            
            point = merge_point(st, restore_b, restore_t, 3.0, self._target_space)
            st.last_sent_point = point
            st.point = point  # Immediate UI update
            
            await publish_override_point(
                self._mqtt, self._manual_override_topic, point,
                enabled=True, space=self._target_space
            )
            
            self._manual_override_enabled = True
            st.manual_override_enabled = True
            
            _LOGGER.info(f"{self.entity_id}: Restored Manual mode")
        
        # Clear saved mode
        self._mode_before_off = None

    async def _manual_control(
        self, 
        st: PicoTargetState, 
        brightness: int | None, 
        temp_k: int | None, 
        transition: float | None
    ) -> None:
        """Manual control - disable automation."""
        # Use saved brightness if not specified
        if brightness is None:
            brightness = self._brightness_before_off or 255
        
        # Use saved temp if TC mode and not specified
        if temp_k is None and self._target_space == SPACE_TC:
            temp_k = self._temperature_before_off
        
        # Clear saved mode
        self._mode_before_off = None

        # Send manual override
        point = merge_point(st, brightness, temp_k, transition, self._target_space)
        st.last_sent_point = point
        st.point = point  # Immediate UI update
        
        await publish_override_point(
            self._mqtt, self._manual_override_topic, point,
            enabled=True, space=self._target_space
        )
        
        self._manual_override_enabled = True
        st.manual_override_enabled = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn light off - save state for smart restore."""
        st = self._state()
        transition = kwargs.get(ATTR_TRANSITION)

        # Sync from coordinator
        self._sync_state_from_coordinator()

        # Save mode BEFORE turning off
        if self._follow_external:
            self._mode_before_off = "follow"
        elif self._automation_override_enabled:
            self._mode_before_off = "device"
        else:
            self._mode_before_off = "manual"
        
        # Save CURRENT brightness/temp (before fade)
        self._brightness_before_off = self.brightness
        if self._target_space == SPACE_TC:
            self._temperature_before_off = self.color_temp_kelvin
        
        _LOGGER.info(
            f"{self.entity_id}: Saving mode={self._mode_before_off}, "
            f"b={self._brightness_before_off}, t={self._temperature_before_off}"
        )
        
        # Turn off via manual override
        point = merge_point(st, 0, None, transition, self._target_space)
        st.last_sent_point = point
        st.point = point  # Immediate UI update
        
        await publish_override_point(
            self._mqtt, self._manual_override_topic, point,
            enabled=True, space=self._target_space
        )
        
        # If follow external was active, also disable automation override
        # This ensures clean state - only manual override is active while off
        if self._mode_before_off == "follow":
            automation_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
            if automation_topic and automation_topic != self._manual_override_topic:
                await publish_override_point(
                    self._mqtt, automation_topic, point,
                    enabled=False, space=self._target_space
                )
                self._automation_override_enabled = False
                st.automation_override_enabled = False

            # Clear follow_external so the switch reflects "off" while light is off
            self._follow_external = False
            self._sync_state_to_coordinator()
            self.coordinator.async_set_updated_data(self.coordinator.data)

        self._manual_override_enabled = True
        st.manual_override_enabled = True
