"""Helper functions for service handlers."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_AUTOMATION_OVERRIDE_TOPIC,
    CONF_MANUAL_OVERRIDE_TOPIC,
    CONF_OVERRIDE_TOPIC,
    CONF_TARGET_SPACE,
    SPACE_TC,
)

if TYPE_CHECKING:
    from .coordinator import PicoCoordinator
    from .models import PicoTargetState
    from .mqtt_client import PicoMqtt

_LOGGER = logging.getLogger(__name__)


def _parse_target_id(unique_id: str) -> str | None:
    """Extract target_id from entity unique_id.
    
    Expected format: {entry_id}::{target_id}::light
    """
    parts = unique_id.split("::")
    if len(parts) >= 3:
        return parts[1]
    return None


def _find_target_config(targets: list[dict], target_id: str) -> dict | None:
    """Find target config by target_id."""
    return next((t for t in targets if t.get("id") == target_id), None)


class ServiceContext:
    """Container for service handler context to avoid passing multiple parameters."""
    
    def __init__(
        self,
        target_id: str,
        coordinator: PicoCoordinator,
        mqtt: PicoMqtt,
        targets: list[dict],
        state: PicoTargetState,
        space: str = SPACE_TC,
    ):
        self.target_id = target_id
        self.coordinator = coordinator
        self.mqtt = mqtt
        self.targets = targets
        self.state = state
        self.space = space  # Target space (TC or BRIGHTNESS)
    
    def get_topic(self, topic_type: str) -> str | None:
        """Get override topic for this target.
        
        Args:
            topic_type: 'manual' or 'automation'
        """
        tcfg = _find_target_config(self.targets, self.target_id)
        if not tcfg:
            _LOGGER.warning("No target config for %s", self.target_id)
            return None
        
        if topic_type == "manual":
            return tcfg.get(CONF_MANUAL_OVERRIDE_TOPIC) or tcfg.get(CONF_OVERRIDE_TOPIC)
        elif topic_type == "automation":
            return tcfg.get(CONF_AUTOMATION_OVERRIDE_TOPIC) or tcfg.get(CONF_OVERRIDE_TOPIC)
        else:
            raise ValueError(f"Invalid topic_type: {topic_type}")


def get_service_context(hass: HomeAssistant, entity_id: str) -> ServiceContext | None:
    """Extract common service context from entity_id.
    
    This eliminates code duplication across all service handlers.
    
    Args:
        hass: Home Assistant instance
        entity_id: Entity ID from service call
        
    Returns:
        ServiceContext if successful, None if validation failed
    """
    # Validate entity exists and is from this integration
    ent_reg = er.async_get(hass)
    ent = ent_reg.async_get(entity_id)
    
    if ent is None or ent.platform != DOMAIN or not ent.unique_id:
        _LOGGER.warning("Entity %s is not a picolightnode entity", entity_id)
        return None
    
    # Parse target_id from unique_id
    target_id = _parse_target_id(ent.unique_id)
    if not target_id:
        _LOGGER.warning("Could not parse target_id for %s (unique_id=%s)", entity_id, ent.unique_id)
        return None
    
    # Get runtime context
    ctx = hass.data.get(DOMAIN, {}).get(ent.config_entry_id)
    if not ctx:
        _LOGGER.warning("No runtime context for %s", entity_id)
        return None
    
    coordinator = ctx["coordinator"]
    mqtt = ctx["mqtt"]
    targets = ctx["targets"]
    
    # Get target state
    state = coordinator.data.get(target_id)
    if not state:
        _LOGGER.warning("No state for target %s", target_id)
        return None
    
    # Get target config to extract space
    tcfg = _find_target_config(targets, target_id)
    space = tcfg.get(CONF_TARGET_SPACE, SPACE_TC) if tcfg else SPACE_TC
    
    return ServiceContext(
        target_id=target_id,
        coordinator=coordinator,
        mqtt=mqtt,
        targets=targets,
        state=state,
        space=space,
    )
