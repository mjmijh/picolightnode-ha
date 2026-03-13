"""Service helper functions for PICOlightnode."""
from __future__ import annotations

from .const import DEFAULT_FADE_S, DEFAULT_TEMP_K, SPACE_TC, SPACE_BRIGHTNESS
from .models import PicoPointTC, PicoTargetState
from .mqtt_client import PicoMqtt


def _clamp01(x: float) -> float:
    """Clamp value to 0..1 range.
    
    Args:
        x: Value to clamp
        
    Returns:
        Clamped value in range [0, 1]
    """
    return max(0.0, min(1.0, x))


def ha_brightness_to_01(brightness_255: int) -> float:
    """Convert Home Assistant brightness (0-255) to 0..1.
    
    Args:
        brightness_255: Brightness value 0-255
        
    Returns:
        Brightness as float 0..1
    """
    return _clamp01(brightness_255 / 255.0)


def brightness_01_to_ha(b01: float) -> int:
    """Convert brightness 0..1 to Home Assistant format (0-255).
    
    Args:
        b01: Brightness as float 0..1
        
    Returns:
        Brightness value 0-255
    """
    return int(round(_clamp01(b01) * 255))


def merge_point(
    state: PicoTargetState,
    brightness_255: int | None,
    temperature_k: int | None,
    fade_s: float | None,
    space: str = SPACE_TC,
) -> PicoPointTC:
    """Merge service parameters with current state to create a point.
    
    Takes service call parameters (brightness, temperature, fade) and merges
    them with the current state, using state values as fallbacks for any
    unspecified parameters.
    
    For BRIGHTNESS-only targets, temperature_k is ignored.
    
    Args:
        state: Current target state
        brightness_255: Brightness 0-255, or None to use current
        temperature_k: Color temperature in Kelvin, or None to use current (ignored for BRIGHTNESS)
        fade_s: Fade duration in seconds, or None to use current
        space: Target space (TC or BRIGHTNESS)
        
    Returns:
        Complete PicoPointTC with all fields populated
    """
    # Use confirmed or optimistic state as base
    base = state.point or state.last_sent_point

    # Extract base values or use defaults
    b01 = base.brightness_01 if base else 1.0
    tk = base.temperature_k if base else DEFAULT_TEMP_K
    fs = base.fade_s if base else DEFAULT_FADE_S

    # Override with service parameters if provided
    if brightness_255 is not None:
        b01 = ha_brightness_to_01(brightness_255)
    
    # Temperature is only used for TC targets
    if space == SPACE_TC and temperature_k is not None:
        tk = int(temperature_k)
    
    if fade_s is not None:
        fs = float(fade_s)

    return PicoPointTC(
        brightness_01=_clamp01(b01), 
        temperature_k=tk if space == SPACE_TC else None,  # None for BRIGHTNESS targets
        fade_s=fs
    )


async def publish_override_point(
    mqttc: PicoMqtt,
    override_topic: str,
    point: PicoPointTC | None,
    enabled: bool,
    space: str = SPACE_TC,
) -> None:
    """Publish override point to MQTT.
    
    When point is provided: Sends full override with brightness/temperature/fade.
    When point is None: Sends ONLY enabled flag (lets PICO/automation decide brightness).
    
    For BRIGHTNESS targets, temperature is omitted from the payload.
    
    Args:
        mqttc: MQTT client
        override_topic: MQTT topic for override
        point: Point to publish (brightness, temperature, fade), or None to not send point
        enabled: Whether override is enabled
        space: Target space (TC or BRIGHTNESS)
    """
    if point is not None:
        # Send full point with enabled flag
        point_data = {
            "space": space,
            "brightness": point.brightness_01,
            "fade": point.fade_s,
        }
        
        # Only include temperature for TC targets
        if space == SPACE_TC and point.temperature_k is not None:
            point_data["temperature"] = point.temperature_k
        
        payload = {
            "enabled": bool(enabled),
            "point": point_data,
        }
    else:
        # Send ONLY enabled flag (no point data)
        payload = {
            "enabled": bool(enabled),
        }
    
    await mqttc.publish_json(override_topic, payload, retain=False)
