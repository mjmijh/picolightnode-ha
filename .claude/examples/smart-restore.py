# Smart Restore Implementation Example

This file shows the complete Smart Restore pattern used in PICOlightnode v2.0.18.

## The Three Modes

```python
# Mode saved in async_turn_off()
self._mode_before_off: str | None
# Values: "follow" | "device" | "manual" | None
```

### Follow External Mode ("follow")
- User was using Keyframe Scheduler (automation override active)
- Needs to restore: automation override enabled + saved brightness
- Follow External Switch: ON

### Device Mode ("device")  
- PICO internal automation was active
- Needs to restore: both overrides disabled
- PICO firmware takes over

### Manual Mode ("manual")
- User had manual control
- Needs to restore: manual override enabled + saved brightness
- Direct user control

---

## Complete Smart Restore Flow

```python
"""
Complete Smart Restore implementation from PICOlightnode v2.0.18.
Shows the full turn_off → turn_on cycle.
"""

from homeassistant.core import Context
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_TRANSITION


async def async_turn_off(self, **kwargs) -> None:
    """
    Turn off light and save current mode.
    
    This is Step 1 of Smart Restore - save the state we need to restore later.
    """
    st = self._state()
    transition = kwargs.get(ATTR_TRANSITION, 2.0)
    
    # === DETERMINE MODE ===
    if self._follow_external:
        # Follow External was active
        self._mode_before_off = "follow"
        self._brightness_before_off = self.brightness  # Save current brightness
        self._temperature_before_off = self.color_temp_kelvin
        
        _LOGGER.debug(
            f"{self.entity_id}: Saving Follow External mode "
            f"(brightness={self.brightness})"
        )
    
    elif self._automation_override_enabled:
        # Internal automation was active (no Follow External)
        self._mode_before_off = "device"
        # Don't save brightness - PICO will use internal automation
        
        _LOGGER.debug(f"{self.entity_id}: Saving Device mode")
    
    else:
        # Manual control
        self._mode_before_off = "manual"
        self._brightness_before_off = self.brightness
        self._temperature_before_off = self.color_temp_kelvin
        
        _LOGGER.debug(
            f"{self.entity_id}: Saving Manual mode "
            f"(brightness={self.brightness})"
        )
    
    # === TURN OFF VIA MANUAL OVERRIDE ===
    # Use brightness=0 with transition
    manual_topic = self._target.get(CONF_MANUAL_OVERRIDE_TOPIC)
    if manual_topic:
        point = merge_point(st, 0, None, transition, self._target_space)
        await publish_override_point(
            self._mqtt, manual_topic, point, enabled=True,
            space=self._target_space
        )
        self._manual_override_enabled = True
        st.manual_override_enabled = True
    
    # === IF FOLLOW WAS ACTIVE: ALSO DISABLE AUTOMATION OVERRIDE ===
    if self._mode_before_off == "follow":
        auto_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
        if auto_topic:
            await publish_override_point(
                self._mqtt, auto_topic, point=None, enabled=False,
                space=self._target_space
            )
            self._automation_override_enabled = False
            st.automation_override_enabled = False
            
            _LOGGER.debug(f"{self.entity_id}: Disabled automation override")
    
    # Sync coordinator
    self.coordinator.async_set_updated_data(self.coordinator.data)
    
    _LOGGER.info(
        f"{self.entity_id}: Turned off, saved mode={self._mode_before_off}"
    )


async def async_turn_on(self, **kwargs) -> None:
    """
    Turn on light with Smart Restore.
    
    This is Step 2 of Smart Restore - check if we have a saved mode and restore it.
    
    CRITICAL: mode_before_off check has ABSOLUTE PRIORITY over brightness parameter!
    """
    st = self._state()
    brightness = kwargs.get(ATTR_BRIGHTNESS)
    transition = kwargs.get(ATTR_TRANSITION, 2.0)
    temp = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
    
    # === CRITICAL: CHECK mode_before_off FIRST! ===
    # This has priority over brightness parameter
    if self._mode_before_off:
        _LOGGER.info(
            f"{self.entity_id}: Smart Restore triggered "
            f"(mode={self._mode_before_off}), ignoring brightness parameter"
        )
        await self._restore_mode(st, transition)
        return  # MUST return - don't proceed to manual control!
    
    # === NO SAVED MODE - MANUAL CONTROL ===
    _LOGGER.debug(f"{self.entity_id}: No saved mode, using manual control")
    await self._manual_control(st, brightness, temp, transition)


async def _restore_mode(self, st, transition):
    """
    Restore the saved mode.
    
    Called from async_turn_on() when mode_before_off exists.
    """
    mode = self._mode_before_off
    self._mode_before_off = None  # Clear after reading
    
    _LOGGER.debug(f"{self.entity_id}: Restoring mode={mode}")
    
    # === MODE: FOLLOW EXTERNAL ===
    if mode == "follow":
        await self._restore_follow_external(st, transition)
    
    # === MODE: DEVICE (PICO INTERNAL) ===
    elif mode == "device":
        await self._restore_device_mode(st)
    
    # === MODE: MANUAL ===
    elif mode == "manual":
        await self._restore_manual_mode(st, transition)


async def _restore_follow_external(self, st, transition):
    """
    Restore Follow External mode.
    
    Steps:
    1. Set follow_external flag
    2. Release manual override
    3. Enable automation override WITH saved brightness
    4. Set Context ID for Blueprint detection
    """
    # Re-enable Follow External flag
    self._follow_external = True
    st.follow_external = True
    self._sync_state_to_coordinator()
    
    _LOGGER.debug(f"{self.entity_id}: Set follow_external=True")
    
    # Get brightness to restore (default to full if missing)
    restore_b = self._brightness_before_off or 255
    restore_temp = self._temperature_before_off
    
    # Create point with saved brightness
    # fade=0.0 → instant set, external automation will override shortly
    point = merge_point(st, restore_b, restore_temp, 0.0, self._target_space)
    
    # Release manual override
    manual_topic = self._target.get(CONF_MANUAL_OVERRIDE_TOPIC)
    if manual_topic:
        await publish_override_point(
            self._mqtt, manual_topic, point=None, enabled=False,
            space=self._target_space
        )
        self._manual_override_enabled = False
        st.manual_override_enabled = False
    
    # Enable automation override WITH saved brightness as initial value
    auto_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
    if auto_topic:
        await publish_override_point(
            self._mqtt, auto_topic, point, enabled=True,
            space=self._target_space
        )
        self._automation_override_enabled = True
        st.automation_override_enabled = True
        
        _LOGGER.debug(
            f"{self.entity_id}: Enabled automation override "
            f"with initial brightness={restore_b}"
        )
    
    # Update coordinator
    self.coordinator.async_set_updated_data(self.coordinator.data)
    
    # === CRITICAL: Set Context ID for Blueprint ===
    # This tells Keyframe Scheduler Blueprint that this is PICO-internal,
    # not a manual user action
    self.async_write_ha_state(
        context=Context(id="picolightnode_restore")
    )
    
    _LOGGER.info(
        f"{self.entity_id}: Restored Follow External mode "
        f"(initial brightness={restore_b}, follow_external=True)"
    )


async def _restore_device_mode(self, st):
    """
    Restore Device mode (PICO internal automation).
    
    Steps:
    1. Release manual override
    2. Release automation override
    3. PICO firmware takes over with internal automation
    """
    manual_topic = self._target.get(CONF_MANUAL_OVERRIDE_TOPIC)
    auto_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
    
    # Release both overrides
    if manual_topic:
        await publish_override_point(
            self._mqtt, manual_topic, point=None, enabled=False,
            space=self._target_space
        )
        self._manual_override_enabled = False
        st.manual_override_enabled = False
    
    if auto_topic:
        await publish_override_point(
            self._mqtt, auto_topic, point=None, enabled=False,
            space=self._target_space
        )
        self._automation_override_enabled = False
        st.automation_override_enabled = False
    
    # Update coordinator
    self.coordinator.async_set_updated_data(self.coordinator.data)
    
    _LOGGER.info(
        f"{self.entity_id}: Restored Device mode (PICO internal automation)"
    )


async def _restore_manual_mode(self, st, transition):
    """
    Restore Manual mode.
    
    Steps:
    1. Enable manual override with saved brightness
    """
    restore_b = self._brightness_before_off or 128  # Default to 50%
    restore_temp = self._temperature_before_off
    
    # Create point with saved brightness
    point = merge_point(st, restore_b, restore_temp, transition, self._target_space)
    
    # Enable manual override
    manual_topic = self._target.get(CONF_MANUAL_OVERRIDE_TOPIC)
    if manual_topic:
        await publish_override_point(
            self._mqtt, manual_topic, point, enabled=True,
            space=self._target_space
        )
        self._manual_override_enabled = True
        st.manual_override_enabled = True
        
        _LOGGER.debug(
            f"{self.entity_id}: Enabled manual override "
            f"with brightness={restore_b}"
        )
    
    # Update coordinator
    self.coordinator.async_set_updated_data(self.coordinator.data)
    
    _LOGGER.info(
        f"{self.entity_id}: Restored Manual mode (brightness={restore_b})"
    )
```

---

## Testing Smart Restore

```python
# Test 1: Follow External Mode
print("Test 1: Follow External Mode")
print("-" * 50)
print("1. Follow External ON, brightness=255")
print("2. Turn OFF → mode_before_off='follow', brightness_before_off=255")
print("3. Turn ON → Restore:")
print("   - follow_external = True")
print("   - automation_override enabled with brightness=255")
print("   - Context ID set to 'picolightnode_restore'")
print("   - Keyframe Scheduler takes over after 1-2 seconds")
print()

# Test 2: Device Mode
print("Test 2: Device Mode")
print("-" * 50)
print("1. No Follow External, no manual changes")
print("2. Turn OFF → mode_before_off='device'")
print("3. Turn ON → Restore:")
print("   - Both overrides disabled")
print("   - PICO internal automation takes over")
print()

# Test 3: Manual Mode
print("Test 3: Manual Mode")
print("-" * 50)
print("1. Manual brightness=128")
print("2. Turn OFF → mode_before_off='manual', brightness_before_off=128")
print("3. Turn ON → Restore:")
print("   - manual_override enabled with brightness=128")
print()

# Test 4: Priority Over Brightness Parameter
print("Test 4: Priority Test")
print("-" * 50)
print("User clicks ON in Dashboard:")
print("  Service call: light.turn_on(brightness=255)")
print()
print("WITHOUT priority check:")
print("  → brightness parameter used")
print("  → manual_control() called")
print("  → Smart Restore bypassed ❌")
print()
print("WITH priority check:")
print("  → mode_before_off checked FIRST")
print("  → _restore_mode() called")
print("  → brightness parameter ignored")
print("  → Smart Restore works ✅")
```

---

## Why Context ID is Critical

```python
# Without Context ID
print("WITHOUT Context ID:")
print("-" * 50)
print("1. User clicks Light ON")
print("2. PICO Smart Restore → brightness changes")
print("3. Keyframe Blueprint sees state change")
print("4. Blueprint checks: user_id=None, parent_id=None")
print("5. Blueprint OLD LOGIC (v3.0.9): has_user and not has_parent")
print("6. Result: Actually this would be False... but somehow triggered")
print("7. Follow External disabled ❌")
print()

# With Context ID
print("WITH Context ID (v2.0.18 + Blueprint v4.0):")
print("-" * 50)
print("1. User clicks Light ON")
print("2. PICO Smart Restore → brightness changes")
print("3. PICO sets Context(id='picolightnode_restore')")
print("4. Keyframe Blueprint sees state change")
print("5. Blueprint checks: context.id contains 'picolightnode'")
print("6. Blueprint NEW LOGIC: from_pico=True")
print("7. Result: NOT manual override")
print("8. Follow External stays ON ✅")
```
