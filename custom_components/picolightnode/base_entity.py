"""Base classes and mixins for PICOlightnode entities."""
from __future__ import annotations

from .const import DOMAIN


class PicoTargetDeviceInfoMixin:
    """Mixin providing consistent device_info for all target entities.
    
    This mixin expects the following instance attributes:
    - _device_id: str
    - _target_id: str  
    - _device_name: str
    - _target_name: str
    """
    
    _device_id: str
    _target_id: str
    _device_name: str
    _target_name: str
    
    @property
    def device_info(self):
        """Return device info for this target entity."""
        return {
            "identifiers": {(DOMAIN, f"{self._device_id}::{self._target_id}")},
            "via_device": (DOMAIN, self._device_id),
            "name": f"{self._device_name} · {self._target_name}",
            "manufacturer": "PICO",
            "model": "lightnode",
        }
