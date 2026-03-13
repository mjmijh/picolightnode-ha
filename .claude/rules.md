# PICOlightnode Development Rules

## Critical Code Patterns

### ✅ Smart Restore Priority (ABSOLUTE RULE!)

```python
async def async_turn_on(self, **kwargs) -> None:
    """Turn on light - Smart Restore has ABSOLUTE PRIORITY."""
    brightness = kwargs.get(ATTR_BRIGHTNESS)
    transition = kwargs.get(ATTR_TRANSITION)
    temp = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
    
    # CRITICAL: Check mode_before_off FIRST!
    # This has priority over brightness parameter!
    if self._mode_before_off:
        await self._restore_mode(st, transition)
        return  # MUST return here!
    
    # Only if no saved mode - manual control
    await self._manual_control(st, brightness, temp, transition)
```

**Why this is CRITICAL:**
- Dashboard sends `brightness` parameter even on simple ON click
- Without priority check, Smart Restore would be bypassed
- User expects mode to be restored, not manual brightness

**Testing:**
```python
# Test case: Follow External enabled, Light OFF, Light ON
# Expected: Follow External stays ON
# Without priority: brightness parameter triggers manual control ❌
# With priority: mode_before_off="follow" restored first ✅
```

---

### ✅ Context on PICO-Internal State Changes

**ALWAYS set context for internal updates:**

```python
# After Smart Restore completes
self.async_write_ha_state(
    context=Context(id="picolightnode_restore")
)

# After MQTT coordinator update (if adding direct state writes)
self.async_write_ha_state(
    context=Context(id="picolightnode_mqtt")
)
```

**Why?**
- Keyframe Scheduler Blueprint needs to distinguish PICO-internal updates
- Without context: Blueprint thinks restore is manual override
- With context: Blueprint knows it's PICO-internal, keeps Follow External ON

**Where to apply:**
- ✅ `_restore_mode()` completion
- ✅ Button entity actions
- ✅ Any programmatic state change (not from user)
- ❌ User Dashboard clicks (use HA default context)

---

### ✅ publish_override_point Usage

```python
async def publish_override_point(
    mqttc,
    override_topic,
    point: PicoPointTC | None,  # None = don't send point data!
    enabled: bool,
    space=SPACE_TC
) -> None:
```

**Usage Patterns:**

**Disable override (no point needed):**
```python
await publish_override_point(mqtt, topic, point=None, enabled=False)
# Sends: {"enabled": false}
```

**Enable with specific brightness:**
```python
point = merge_point(st, brightness, temp, fade, space)
await publish_override_point(mqtt, topic, point, enabled=True)
# Sends: {"enabled": true, "point": {"brightness": 0.75, ...}}
```

**❌ CRITICAL BUG - Follow External Restore:**
```python
# WRONG - Would activate PICO defaultpoint!
await publish_override_point(mqtt, auto_topic, point=None, enabled=True)
```

**✅ CORRECT - Follow External Restore:**
```python
# Send saved brightness as initial value
point = merge_point(st, brightness_before_off, temp_before_off, 0.0, space)
await publish_override_point(mqtt, auto_topic, point, enabled=True)
# External automation will override shortly, but starts at saved brightness
```

---

### ✅ Correct Config Constant

**❌ WRONG:**
```python
automation_topic = self._target.get(CONF_OVERRIDE_TOPIC)
# This key doesn't exist!
```

**✅ CORRECT:**
```python
from .const import CONF_AUTOMATION_OVERRIDE_TOPIC

automation_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
# CONF_AUTOMATION_OVERRIDE_TOPIC = "automation_override_topic"
```

**This was a v2.0.17 bug:**
- Code used `CONF_OVERRIDE_TOPIC` (wrong key name)
- Config has `automation_override_topic` key
- Result: automation_topic was None
- Follow External didn't work!

---

### ✅ follow_external Management

**ONLY set from HA entities:**

```python
# In Light Entity or Switch Entity - ✅ CORRECT
self._follow_external = True
st.follow_external = True
self._sync_state_to_coordinator()
```

**NEVER from MQTT handlers:**

```python
# In Coordinator MQTT handler - ❌ WRONG!
def _handle_mqtt_message(self, payload):
    st.manual_override_enabled = payload.get("manual_enabled")  # ✅ OK
    st.follow_external = False  # ❌ NEVER DO THIS!
```

**Why?**
- `follow_external` is a **User Setting** (HA-side)
- NOT a PICO hardware state
- PICO doesn't know which override is "follow external"
- Can be "out of sync" if external apps change overrides (acceptable trade-off)

**Design Decision:**
- Option A: follow_external is User Setting (CHOSEN)
- Option B: Sync from PICO MQTT (would need firmware update)

---

## Error Prevention Checklist

Before committing changes:

**Smart Restore:**
- [ ] `mode_before_off` checked FIRST in `async_turn_on`
- [ ] Returns immediately if mode found
- [ ] All three modes implemented (follow/device/manual)
- [ ] Context ID set after restore completion

**Context Tracking:**
- [ ] Context ID set on all PICO-internal updates
- [ ] Context NOT set on user Dashboard clicks
- [ ] Context ID consistent: `picolightnode_restore`

**MQTT:**
- [ ] Using `CONF_AUTOMATION_OVERRIDE_TOPIC` (not `CONF_OVERRIDE_TOPIC`)
- [ ] `point=None` when disabling overrides
- [ ] `point=value` when enabling Follow External restore
- [ ] Never send `enabled=true` without point for Follow External

**State Management:**
- [ ] `follow_external` only set from entities (never from MQTT)
- [ ] Coordinator sync called after state changes
- [ ] RestoreEntity used for persistence

---

## Common Bugs

### Bug: Follow External disabled after restore
**Symptom:** Switch goes OFF right after turning light ON
**Root Cause:** Keyframe Blueprint detected restore as manual override
**Check:** 
- Is Context ID set? (`picolightnode_restore`)
- Is Blueprint v4.0+? (has PICO context detection)
- Check logs for context.id in state changes

**Fix:** Upgrade to v2.0.18+ PICOlightnode + Blueprint v4.0

---

### Bug: automation_override_topic not found
**Symptom:** Follow External Switch does nothing, logs show "No automation override topic"
**Root Cause:** Using wrong config constant `CONF_OVERRIDE_TOPIC`
**Check:**
```python
# In light_entity.py or switch_entity.py
automation_topic = self._target.get(???)
# Should be CONF_AUTOMATION_OVERRIDE_TOPIC
```

**Fix:** Use `CONF_AUTOMATION_OVERRIDE_TOPIC` everywhere

---

### Bug: Light doesn't restore to Follow External
**Symptom:** Light turns on at manual brightness, not Follow External
**Root Cause:** Smart Restore priority not enforced
**Check:**
```python
async def async_turn_on(self, **kwargs):
    # Is this FIRST?
    if self._mode_before_off:
        await self._restore_mode(...)
        return  # Does it return?
```

**Fix:** Ensure mode_before_off check is FIRST, returns immediately

---

### Bug: Light goes to PICO defaultpoint on restore
**Symptom:** Light restores to wrong brightness (from setup.json defaultpoint)
**Root Cause:** Sending `enabled=true` WITHOUT point
**Check:**
```python
# Follow External restore - is point provided?
await publish_override_point(mqtt, auto_topic, point, enabled=True)
# point should be merge_point(...) not None!
```

**Fix:** Always send saved brightness as initial value

---

## Mode Save/Restore Patterns

### Save Mode on Turn Off
```python
async def async_turn_off(self, **kwargs) -> None:
    """Save current mode before turning off."""
    st = self._state()
    
    # Determine mode
    if self._follow_external:
        self._mode_before_off = "follow"
        self._brightness_before_off = self.brightness
        self._temperature_before_off = self.color_temp_kelvin
    elif self._automation_override_enabled:
        self._mode_before_off = "device"
        # No brightness needed - PICO will use internal automation
    else:
        self._mode_before_off = "manual"
        self._brightness_before_off = self.brightness
        self._temperature_before_off = self.color_temp_kelvin
    
    # Turn off via manual override with brightness=0
    point = merge_point(st, 0, None, transition, self._target_space)
    await publish_override_point(mqtt, manual_topic, point, True)
    
    # If Follow was active, also disable automation override
    if self._mode_before_off == "follow":
        await publish_override_point(mqtt, auto_topic, None, False)
```

---

### Restore Mode on Turn On
```python
async def _restore_mode(self, st, transition):
    """Restore saved mode."""
    mode = self._mode_before_off
    self._mode_before_off = None  # Clear after reading
    
    if mode == "follow":
        # Re-enable Follow External
        self._follow_external = True
        st.follow_external = True
        self._sync_state_to_coordinator()
        
        # Send saved brightness as initial value
        point = merge_point(
            st,
            self._brightness_before_off or 255,
            self._temperature_before_off,
            0.0,  # No transition - instant
            self._target_space
        )
        
        # Release manual override
        await publish_override_point(mqtt, manual_topic, None, False)
        
        # Enable automation override WITH saved brightness
        await publish_override_point(mqtt, auto_topic, point, True)
        
        self._automation_override_enabled = True
        st.automation_override_enabled = True
        
        # Sync coordinator
        self.coordinator.async_set_updated_data(self.coordinator.data)
        
        # Set context for Blueprint detection
        self.async_write_ha_state(
            context=Context(id="picolightnode_restore")
        )
        
        _LOGGER.info(
            f"{self.entity_id}: Restored Follow External mode "
            f"(brightness={self._brightness_before_off})"
        )
    
    elif mode == "device":
        # Release both overrides → PICO internal automation
        await publish_override_point(mqtt, manual_topic, None, False)
        await publish_override_point(mqtt, auto_topic, None, False)
        
        self._manual_override_enabled = False
        self._automation_override_enabled = False
        st.manual_override_enabled = False
        st.automation_override_enabled = False
        
        _LOGGER.info(f"{self.entity_id}: Restored Device mode (PICO internal)")
    
    elif mode == "manual":
        # Restore saved brightness via manual override
        point = merge_point(
            st,
            self._brightness_before_off or 128,
            self._temperature_before_off,
            transition,
            self._target_space
        )
        await publish_override_point(mqtt, manual_topic, point, True)
        
        self._manual_override_enabled = True
        st.manual_override_enabled = True
        
        _LOGGER.info(
            f"{self.entity_id}: Restored Manual mode "
            f"(brightness={self._brightness_before_off})"
        )
```

---

## MQTT Payload Examples

### Turn Off (Manual Override)
```json
// Topic: {target}/override/manual
{
  "enabled": true,
  "point": {
    "brightness": 0.0,
    "temperature": 3500,
    "fade": 2.0
  }
}
```

### Follow External Restore
```json
// 1. Release manual
// Topic: {target}/override/manual
{
  "enabled": false
}

// 2. Enable automation with saved brightness
// Topic: {target}/override/automation
{
  "enabled": true,
  "point": {
    "brightness": 1.0,   // Saved value!
    "temperature": 4000,
    "fade": 0.0
  }
}
```

### Device Mode Restore
```json
// 1. Release manual
// Topic: {target}/override/manual
{
  "enabled": false
}

// 2. Release automation
// Topic: {target}/override/automation
{
  "enabled": false
}

// PICO internal automation takes over
```

---

## Testing Checklist

**Manual Only Mode:**
```
1. Follow External OFF
2. Set brightness to 50%
3. Light OFF
4. Light ON
Expected: Brightness 50% ✅
```

**Device Mode:**
```
1. Follow External OFF
2. No manual changes (or reset all overrides)
3. Light OFF
4. Light ON
Expected: PICO internal automation active ✅
```

**Follow External Mode:**
```
1. Follow External ON
2. Keyframe Scheduler running
3. Light OFF
4. Light ON
Expected: 
- Light starts at saved brightness
- Follow External Switch stays ON ✅
- Keyframe takes over after 1-2 seconds ✅
```

**Manual Override Detection:**
```
1. Follow External ON
2. Change brightness in Dashboard
Expected: Follow External goes OFF automatically ✅
(requires Blueprint v4.0)
```

---

For complete architecture and workflows, see `architecture.md` and `PICO_KEYFRAME_CONCEPT.md`.
