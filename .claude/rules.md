# PICOlightnode Development Rules

## Critical Code Patterns

### ✅ Smart Restore Priority (MUST FOLLOW!)
```python
async def async_turn_on(self, **kwargs):
    # CHECK FIRST - mode_before_off has ABSOLUTE PRIORITY
    if self._mode_before_off:
        await self._restore_mode(st, transition)
        return  # MUST return here!
    
    # Only if no saved mode:
    await self._manual_control(st, brightness, temp, transition)
```

**Why?** Dashboard sends brightness parameter even on simple ON click. Without priority check, Smart Restore would be bypassed!

---

### ✅ Context on State Changes
```python
# ALL PICO-internal state updates
self.async_write_ha_state(
    context=Context(id="picolightnode_restore")
)
```

**Where to apply:**
- ✅ Smart Restore completion
- ✅ MQTT state updates (if we add direct state writes)
- ✅ Button entity actions
- ❌ User Dashboard clicks (use HA default)

---

### ✅ publish_override_point Usage

**Disable override (no point):**
```python
await publish_override_point(mqtt, topic, point=None, enabled=False)
# Sends: {"enabled": false}
```

**Enable with specific brightness:**
```python
point = merge_point(st, brightness, temp, fade)
await publish_override_point(mqtt, topic, point, enabled=True)
# Sends: {"enabled": true, "point": {"brightness": 0.5, ...}}
```

**❌ NEVER for Follow External restore:**
```python
# This activates PICO defaultpoint!
await publish_override_point(mqtt, topic, point=None, enabled=True)
```

**✅ ALWAYS for Follow External restore:**
```python
# Send saved brightness as initial value
point = merge_point(st, brightness_before_off, temp_before_off, 0.0)
await publish_override_point(mqtt, topic, point, enabled=True)
```

---

### ✅ Correct Config Constant
```python
# ❌ WRONG - legacy, doesn't exist in config
automation_topic = self._target.get(CONF_OVERRIDE_TOPIC)

# ✅ CORRECT
automation_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
```

---

### ✅ follow_external Management

**Set ONLY from HA entities:**
```python
# In Light Entity or Switch Entity
self._follow_external = True
st.follow_external = True
self._sync_state_to_coordinator()
```

**❌ NEVER from MQTT handlers:**
```python
# In Coordinator - DO NOT set follow_external
# It's a User Setting, not PICO state
def _on_override(payload):
    st.manual_override_enabled = payload["enabled"]  # ✅ OK
    st.follow_external = False  # ❌ NEVER DO THIS
```

---

## Error Prevention Checklist

Before committing changes:

**Smart Restore:**
- [ ] mode_before_off checked FIRST in async_turn_on
- [ ] Returns immediately if mode found (doesn't continue to manual control)
- [ ] All three modes (follow/device/manual) implemented

**Context Tracking:**
- [ ] Context ID set on all PICO-internal state changes
- [ ] Context NOT set on user Dashboard clicks
- [ ] Blueprint can distinguish sources

**MQTT:**
- [ ] Using CONF_AUTOMATION_OVERRIDE_TOPIC (not CONF_OVERRIDE_TOPIC)
- [ ] point=None when disabling
- [ ] point=value when enabling Follow External restore

**State Management:**
- [ ] follow_external only set from entities
- [ ] Coordinator sync called after changes
- [ ] RestoreEntity used for persistence

---

## Common Bugs

### Bug: Follow External disabled after restore
**Symptom:** Switch goes OFF right after turning light ON
**Cause:** Blueprint detected restore as manual override
**Check:** Is Context ID set? Is Blueprint v4.0+?

### Bug: Light doesn't follow Keyframe
**Symptom:** Light stays at one brightness
**Cause:** automation_override not enabled
**Check:** Is automation_topic found? Check CONF_AUTOMATION_OVERRIDE_TOPIC

### Bug: Mode not restored after HA restart
**Symptom:** Smart Restore forgets mode
**Cause:** RestoreEntity not implemented or attributes not exposed
**Check:** Is RestoreEntity base class used? Are attributes in extra_state_attributes?