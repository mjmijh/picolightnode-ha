"""Data coordinator for PICOlightnode."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .mqtt_client import PicoMqtt
from .models import PicoPointTC, PicoTargetState

_LOGGER = logging.getLogger(__name__)


def _normalize_brightness_to_01(b: Any) -> float | None:
    """Normalize brightness to 0..1.
    
    Accepts:
      - 0..1 floats
      - 0..100 percent
      - 0..255 HA brightness
      
    Args:
        b: Brightness value in any supported format
        
    Returns:
        Normalized brightness 0..1 or None if invalid
    """
    try:
        bf = float(b)
    except (TypeError, ValueError):
        return None

    if bf <= 1.0:
        return max(0.0, min(1.0, bf))
    if bf <= 100.0:
        return max(0.0, min(1.0, bf / 100.0))
    if bf <= 255.0:
        return max(0.0, min(1.0, bf / 255.0))
    
    # Value > 255 is unexpected, log warning
    _LOGGER.warning("Unexpected brightness value: %s, clamping to 1.0", bf)
    return 1.0


def _extract_fields(payload: dict[str, Any]) -> tuple[float | None, int | None, float | None]:
    """Extract brightness/temp/fade from MQTT payload.
    
    Supports both direct fields and nested 'point' object.
    Temperature can be in 'temperature' or 'cct' field.
    
    Args:
        payload: MQTT message payload dict
        
    Returns:
        Tuple of (brightness_01, temperature_k, fade_s)
    """
    # Check if fields are nested in 'point' object
    p = payload.get("point") if isinstance(payload.get("point"), dict) else payload

    # Extract brightness
    b_raw = p.get("brightness")
    b01 = _normalize_brightness_to_01(b_raw) if b_raw is not None else None

    # Extract temperature (supports both 'temperature' and 'cct' field names)
    t_raw = p.get("temperature")
    if t_raw is None:
        t_raw = p.get("cct")

    temp_k: int | None = None
    if t_raw is not None:
        try:
            temp_k = int(float(t_raw))
        except (TypeError, ValueError):
            temp_k = None

    # Extract fade
    fade_raw = p.get("fade")
    fade_s: float | None = None
    if fade_raw is not None:
        try:
            fade_s = float(fade_raw)
        except (TypeError, ValueError):
            fade_s = None

    return b01, temp_k, fade_s


class PicoCoordinator(DataUpdateCoordinator[dict[str, PicoTargetState]]):
    """Coordinator for PICOlightnode device state.
    
    Subscribes to MQTT topics for each configured target and maintains
    the current state (brightness, temperature, overrides).
    
    Thread-safe updates using asyncio.Lock to prevent race conditions
    when multiple MQTT messages arrive simultaneously.
    """
    
    def __init__(
        self,
        hass: HomeAssistant,
        mqttc: PicoMqtt,
        targets: list[dict[str, Any]],
    ) -> None:
        """Initialize coordinator.
        
        Args:
            hass: Home Assistant instance
            mqttc: MQTT client wrapper
            targets: List of target configurations
        """
        super().__init__(
            hass, 
            logger=_LOGGER, 
            name="picolightnode", 
            update_interval=None  # Event-driven via MQTT
        )
        self._mqtt = mqttc
        self._targets = targets
        self._unsubs: list[callable] = []
        self._update_lock = asyncio.Lock()
        
        # CRITICAL: Initialize data AFTER super().__init__()
        # DataUpdateCoordinator sets self.data = None in its __init__
        # We must override it here to ensure it's never None
        self.data: dict[str, PicoTargetState] = {
            t["id"]: PicoTargetState() for t in targets
        }
        
        # Notify that data is ready
        self.async_set_updated_data(self.data)

    async def async_start(self) -> None:
        """Start MQTT subscriptions for all targets."""
        for t in self._targets:
            target_id = t["id"]
            state_topic = t["state_topic"]

            # Subscribe to device state topic
            async def _on_state(
                _topic: str, 
                payload: dict[str, Any], 
                *, 
                _tid: str = target_id
            ) -> None:
                """Handle state update from device."""
                async with self._update_lock:  # Thread-safe state updates
                    st = self.data[_tid]

                    b01, temp_k, fade_s = _extract_fields(payload)

                    _LOGGER.debug("PICO state msg (%s): %s", _topic, payload)
                    _LOGGER.debug(
                        "Parsed fields for %s: b01=%s temp_k=%s fade_s=%s", 
                        _tid, b01, temp_k, fade_s
                    )

                    # Merge partial fields (device may publish brightness and cct separately)
                    if b01 is not None:
                        st.last_brightness_01 = b01
                    if temp_k is not None:
                        st.last_temperature_k = temp_k
                    if fade_s is not None:
                        st.last_fade_s = fade_s

                    # Compose full point when both brightness and temperature are known
                    if st.last_brightness_01 is not None and st.last_temperature_k is not None:
                        st.point = PicoPointTC(
                            brightness_01=st.last_brightness_01,
                            temperature_k=st.last_temperature_k,
                            fade_s=st.last_fade_s or 0.0,
                        )

                    # Extract override_enabled if available (often not in firmware state)
                    override_enabled = payload.get("override_enabled")
                    if override_enabled is None and isinstance(payload.get("override"), dict):
                        override_enabled = payload["override"].get("enabled")
                    if override_enabled is not None:
                        st.override_enabled = bool(override_enabled)

                    # Trigger entity updates
                    self.async_set_updated_data(self.data)

            unsub_state = await self._mqtt.subscribe_json(state_topic, _on_state)
            self._unsubs.append(unsub_state)

            # Subscribe to override topics (best-effort, observed on MQTT)
            manual_topic = t.get("manual_override_topic") or t.get("override_topic")
            automation_topic = t.get("automation_override_topic")

            async def _on_override(
                _topic: str, 
                payload: dict[str, Any], 
                *, 
                _tid: str, 
                _kind: str
            ) -> None:
                """Handle override state update (manual or automation)."""
                async with self._update_lock:
                    st = self.data[_tid]
                    
                    # Extract enabled flag
                    enabled = payload.get("enabled")
                    if enabled is None and isinstance(payload.get("override"), dict):
                        enabled = payload["override"].get("enabled")
                    if enabled is None:
                        return

                    # Update corresponding override state
                    if _kind == "manual":
                        st.manual_override_enabled = bool(enabled)
                    else:
                        st.automation_override_enabled = bool(enabled)

                    self.async_set_updated_data(self.data)

            # Subscribe to manual override topic
            if manual_topic:
                unsub_m = await self._mqtt.subscribe_json(
                    manual_topic,
                    lambda tp, pl, _tid=target_id: _on_override(tp, pl, _tid=_tid, _kind="manual"),
                )
                self._unsubs.append(unsub_m)

            # Subscribe to automation override topic
            if automation_topic:
                unsub_a = await self._mqtt.subscribe_json(
                    automation_topic,
                    lambda tp, pl, _tid=target_id: _on_override(tp, pl, _tid=_tid, _kind="automation"),
                )
                self._unsubs.append(unsub_a)

    async def async_stop(self) -> None:
        """Unsubscribe from all MQTT topics."""
        for u in self._unsubs:
            try:
                u()
            except Exception:
                pass
        self._unsubs = []
