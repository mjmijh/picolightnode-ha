"""Switch entity for PICOlightnode."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .base_entity import PicoTargetDeviceInfoMixin
from .coordinator import PicoCoordinator
from .models import PicoTargetState
from .mqtt_client import PicoMqtt
from .services import merge_point, publish_override_point

_LOGGER = logging.getLogger(__name__)


class PicoFollowExternalSwitch(
    CoordinatorEntity[PicoCoordinator],
    PicoTargetDeviceInfoMixin,
    RestoreEntity,
    SwitchEntity
):
    """Switch to enable/disable following external automations - v2.0.11.
    
    When ON: Manual override is released, allowing external automation (Keyframer/CCT)
    When OFF: Automation override is released, blocking external automation
    
    Uses RestoreEntity to persist state across HA restarts.
    """

    _attr_icon = "mdi:link-variant"
    
    def __init__(
        self,
        coordinator: PicoCoordinator,
        mqttc: PicoMqtt,
        entry_id: str,
        device_id: str,
        device_name: str,
        name: str,
        unique_id: str,
        target_id: str,
        target_name: str,
        manual_override_topic: str | None,
        automation_override_topic: str | None,
    ) -> None:
        """Initialize follow external switch.
        
        Args:
            coordinator: Data coordinator
            mqttc: MQTT client
            entry_id: Config entry ID
            device_id: Parent device ID
            device_name: Parent device name
            name: Entity name
            unique_id: Unique entity ID
            target_id: Target ID
            target_name: Target name
            manual_override_topic: MQTT topic for manual override
            automation_override_topic: MQTT topic for automation override
        """
        super().__init__(coordinator)
        self._mqtt = mqttc
        self._entry_id = entry_id
        self._device_id = device_id
        self._device_name = device_name
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._target_id = target_id
        self._target_name = target_name
        self._manual_override_topic = manual_override_topic
        self._automation_override_topic = automation_override_topic
        
        # Persistent state - restored from last_state
        self._follow_external: bool = False

    async def async_added_to_hass(self) -> None:
        """Entity added to HA - restore state."""
        await super().async_added_to_hass()
        
        # Restore persistent state
        old_state = await self.async_get_last_state()
        if old_state and old_state.state in ("on", "off"):
            self._follow_external = old_state.state == "on"
            
            # Sync to coordinator
            st = self._state()
            st.follow_external = self._follow_external
            
            _LOGGER.info(
                f"{self.entity_id}: Restored follow_external={self._follow_external}"
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        st = self._state()
        old_state = self._follow_external
        self._follow_external = st.follow_external

        if old_state != self._follow_external:
            _LOGGER.debug(
                "%s: follow_external %s → %s",
                self.entity_id, old_state, self._follow_external
            )

        self.async_write_ha_state()

    def _state(self) -> PicoTargetState:
        """Get current target state from coordinator."""
        if self.coordinator.data is None:
            return PicoTargetState()
        return self.coordinator.data.get(self._target_id, PicoTargetState())

    @property
    def is_on(self) -> bool:
        """Return true if following external automation."""
        return self._follow_external

    async def async_turn_on(self, **kwargs) -> None:
        """Enable following external automation.
        
        Releases manual override so automation can control the light.
        """
        st = self._state()
        
        # Update persistent state
        self._follow_external = True
        st.follow_external = True
        
        # Notify coordinator
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # Release manual override to allow external automation
        if not self._manual_override_topic:
            _LOGGER.debug("No manual override topic for %s; nothing to release", self._target_id)
            return

        try:
            point = merge_point(st, brightness_255=0, temperature_k=None, fade_s=3.0)
            await publish_override_point(self._mqtt, self._manual_override_topic, point, enabled=False)
            _LOGGER.info(f"{self.entity_id}: Follow External enabled")
        except Exception as err:
            _LOGGER.warning("Failed to release manual override for %s: %s", self._target_id, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable following external automation.
        
        Releases automation override so it cannot force values.
        """
        st = self._state()
        
        # Update persistent state
        self._follow_external = False
        st.follow_external = False
        
        # Notify coordinator
        self.coordinator.async_set_updated_data(self.coordinator.data)

        # Release automation override to block external automation
        if not self._automation_override_topic:
            _LOGGER.debug("No automation override topic for %s; nothing to release", self._target_id)
            return

        try:
            point = merge_point(st, brightness_255=0, temperature_k=None, fade_s=3.0)
            await publish_override_point(self._mqtt, self._automation_override_topic, point, enabled=False)
            _LOGGER.info(f"{self.entity_id}: Follow External disabled")
        except Exception as err:
            _LOGGER.warning("Failed to release automation override for %s: %s", self._target_id, err)
