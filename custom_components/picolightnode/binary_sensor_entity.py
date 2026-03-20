from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PicoCoordinator


class _BasePicoBinary(CoordinatorEntity[PicoCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: PicoCoordinator,
        entry_id: str,
        device_id: str,
        device_name: str,
        target_id: str,
        target_name: str,
        unique_id: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._device_id = device_id
        self._device_name = device_name
        self._target_id = target_id
        self._target_name = target_name
        self._attr_unique_id = unique_id
        self._attr_name = name

    @property
    def available(self) -> bool:
        return True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._device_id}::{self._target_id}")},
            "via_device": (DOMAIN, self._device_id),
            "name": f"{self._device_name} · {self._target_name}",
            "manufacturer": "PICO",
            "model": "lightnode",
        }

    def _state(self):
        return self.coordinator.data[self._target_id]


class PicoManualOverrideActive(_BasePicoBinary):
    _attr_icon = "mdi:hand-back-right"

    @property
    def is_on(self):
        v = self._state().manual_override_enabled
        return None if v is None else bool(v)


class PicoAutomationOverrideActive(_BasePicoBinary):
    _attr_icon = "mdi:robot"

    @property
    def is_on(self):
        v = self._state().automation_override_enabled
        return None if v is None else bool(v)
