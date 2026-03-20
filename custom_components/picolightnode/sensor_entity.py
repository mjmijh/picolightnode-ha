"""Sensor entities for PICOlightnode."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfTemperature, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base_entity import PicoTargetDeviceInfoMixin
from .coordinator import PicoCoordinator
from .models import PicoTargetState


class _BasePicoSensor(
    CoordinatorEntity[PicoCoordinator],
    PicoTargetDeviceInfoMixin,
    SensorEntity
):
    """Base class for PICOlightnode sensors."""
    
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: PicoCoordinator,
        entry_id: str,
        device_id: str,
        device_name: str,
        unique_id: str,
        target_id: str,
        target_name: str,
        name: str,
    ) -> None:
        """Initialize sensor.
        
        Args:
            coordinator: Data coordinator
            entry_id: Config entry ID
            device_id: Parent device ID
            device_name: Parent device name
            unique_id: Unique entity ID
            target_id: Target ID
            target_name: Target name
            name: Entity name
        """
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._device_id = device_id
        self._device_name = device_name
        self._attr_unique_id = unique_id
        self._target_id = target_id
        self._target_name = target_name
        self._attr_name = name

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    def _state(self) -> PicoTargetState:
        """Get current target state from coordinator."""
        return self.coordinator.data[self._target_id]

    def _brightness_01(self) -> float | None:
        """Get current brightness (0..1) from state.
        
        Returns:
            Brightness value 0..1 or None if not available
        """
        st = self._state()
        
        # Prefer confirmed point, fallback to partial state
        if st.point is not None:
            return st.point.brightness_01
        return st.last_brightness_01

    def _temperature_k(self) -> int | None:
        """Get current color temperature in Kelvin from state.
        
        Returns:
            Temperature in Kelvin or None if not available
        """
        st = self._state()
        
        # Prefer confirmed point, fallback to partial state
        if st.point is not None:
            return st.point.temperature_k
        return st.last_temperature_k


class PicoDimSensor(_BasePicoSensor):
    """Sensor showing brightness as percentage."""
    
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        """Return brightness as percentage (0-100)."""
        b = self._brightness_01()
        if b is None:
            return None
        return round(float(b) * 100.0, 1)


class PicoCctSensor(_BasePicoSensor):
    """Sensor showing color temperature in Kelvin."""
    
    _attr_native_unit_of_measurement = UnitOfTemperature.KELVIN

    @property
    def native_value(self) -> int | None:
        """Return color temperature in Kelvin."""
        t = self._temperature_k()
        if t is None:
            return None
        return int(round(float(t), 0))
