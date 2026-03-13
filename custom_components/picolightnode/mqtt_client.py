"""MQTT client wrapper for PICOlightnode."""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PicoMqtt:
    """Wrapper around Home Assistant MQTT integration."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize MQTT wrapper.
        
        Args:
            hass: Home Assistant instance
        """
        self.hass = hass

    async def subscribe_json(
        self,
        topic: str,
        handler: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> Callable[[], None]:
        """Subscribe to MQTT topic with JSON payload parsing.
        
        Args:
            topic: MQTT topic to subscribe to
            handler: Async callback receiving (topic, payload_dict)
            
        Returns:
            Unsubscribe callable
        """
        async def _cb(msg: mqtt.ReceiveMessage) -> None:
            # Parse JSON payload
            try:
                payload = json.loads(msg.payload)
            except json.JSONDecodeError:
                _LOGGER.debug(
                    "Invalid JSON in MQTT message on %s: %s", 
                    msg.topic, 
                    msg.payload
                )
                return
            
            # Validate payload is dict
            if not isinstance(payload, dict):
                _LOGGER.debug(
                    "Non-dict payload on %s (type=%s): %s", 
                    msg.topic,
                    type(payload).__name__,
                    payload
                )
                return
            
            # Call handler (log exceptions, don't swallow them)
            try:
                await handler(msg.topic, payload)
            except Exception:
                _LOGGER.exception(
                    "Error in MQTT handler for topic %s with payload: %s",
                    msg.topic,
                    payload
                )

        return await mqtt.async_subscribe(self.hass, topic, _cb)

    async def publish_json(
        self, 
        topic: str, 
        payload: dict[str, Any], 
        retain: bool = False
    ) -> None:
        """Publish JSON payload to MQTT topic.
        
        Args:
            topic: MQTT topic to publish to
            payload: Dictionary to serialize as JSON
            retain: Whether to retain the message
        """
        await mqtt.async_publish(
            self.hass,
            topic,
            json.dumps(payload),
            qos=0,
            retain=retain,
        )
