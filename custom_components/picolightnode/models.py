from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PicoPointTC:
    """PICO point representation.
    
    Supports both TC (Tunable White) and BRIGHTNESS modes.
    For BRIGHTNESS-only targets, temperature_k is None.
    """
    brightness_01: float
    temperature_k: int | None  # None for BRIGHTNESS-only targets
    fade_s: float


@dataclass
class PicoTargetState:
    # Confirmed from device (composed once both brightness + temperature are known)
    point: Optional[PicoPointTC] = None

    # Partial state cache (because device may publish brightness and cct in separate MQTT messages)
    last_brightness_01: Optional[float] = None
    last_temperature_k: Optional[int] = None
    last_fade_s: Optional[float] = None

    # Confirmed from device if available
    override_enabled: Optional[bool] = None

    # Best-effort (observed from MQTT messages sent to override topics)
    manual_override_enabled: Optional[bool] = None
    automation_override_enabled: Optional[bool] = None

    # Local gate for external automation (Keyframer/CCT Astronomy)
    follow_external: bool = False

    # Optimistic fallback for turn_on/turn_off (until next device state arrives)
    last_sent_point: Optional[PicoPointTC] = None
    
    # NEW: Track state before manual override turn-off
    # This allows restoring automation when turning back on
    mode_before_manual_off: Optional[str] = None  # "internal_auto", "external_auto", or None
    point_before_manual_off: Optional[PicoPointTC] = None  # Last point before manual off
