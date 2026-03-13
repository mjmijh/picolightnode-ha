"""Smart Restore Implementation Example"""

async def async_turn_off(self, **kwargs) -> None:
    """Save mode BEFORE turning off."""
    # Determine current mode
    if self._follow_external:
        self._mode_before_off = "follow"
        self._brightness_before_off = self.brightness
        self._temperature_before_off = self.color_temp_kelvin
    elif self._automation_override_enabled:
        self._mode_before_off = "device"
    else:
        self._mode_before_off = "manual"
        self._brightness_before_off = self.brightness
        self._temperature_before_off = self.color_temp_kelvin
    
    # Turn off via manual override
    point = merge_point(st, 0, None, transition, self._target_space)
    await publish_override_point(mqtt, manual_topic, point, True)
    
    # If Follow was active, also disable automation override
    if self._mode_before_off == "follow":
        await publish_override_point(mqtt, auto_topic, None, False)


async def async_turn_on(self, **kwargs) -> None:
    """PRIORITY: Restore mode if saved."""
    brightness = kwargs.get(ATTR_BRIGHTNESS)
    transition = kwargs.get(ATTR_TRANSITION)
    
    # CRITICAL: Check mode_before_off FIRST!
    if self._mode_before_off:
        await self._restore_mode(st, transition)
        return  # Don't proceed to manual control
    
    # No saved mode - manual control
    await self._manual_control(st, brightness, temp, transition)


async def _restore_mode(self, st, transition):
    """Restore to saved mode."""
    mode = self._mode_before_off
    self._mode_before_off = None  # Clear after reading
    
    if mode == "follow":
        # Re-enable Follow External
        self._follow_external = True
        st.follow_external = True
        
        # Send saved brightness as initial value
        point = merge_point(st, self._brightness_before_off, 
                          self._temperature_before_off, 0.0)
        
        # Release manual, enable automation WITH point
        await publish_override_point(mqtt, manual_topic, None, False)
        await publish_override_point(mqtt, auto_topic, point, True)
        
        # Set context for Blueprint
        self.async_write_ha_state(
            context=Context(id="picolightnode_restore")
        )
    
    elif mode == "device":
        # Release both overrides → PICO internal automation
        await publish_override_point(mqtt, manual_topic, None, False)
        await publish_override_point(mqtt, auto_topic, None, False)
    
    elif mode == "manual":
        # Restore to saved brightness via manual override
        point = merge_point(st, self._brightness_before_off,
                          self._temperature_before_off, transition)
        await publish_override_point(mqtt, manual_topic, point, True)