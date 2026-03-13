# PICOlightnode Development Instructions

## Project Type
Home Assistant Custom Integration for PICO Lighting Hardware (MQTT-based control)

## Current Version
v2.0.18 - Context Tracking + Smart Restore

## What This Integration Does
- Controls PICO lighting hardware via MQTT
- Provides Light entities with brightness and color temperature control
- Implements Smart Restore (remembers mode before turn-off)
- Supports three automation levels: Manual, Internal (PICO firmware), External (Follow External)
- Context Tracking for Blueprint integration

## Development Focus
- Smart Restore has absolute priority
- Context Tracking for all PICO-internal updates
- Follow External is User Setting (HA-only, never set from MQTT)
- MQTT override management (manual_override, automation_override)
- Integration with Keyframe Scheduler Blueprint

## Key Principles

### 1. Smart Restore Priority Rule
```python
# IN async_turn_on() - CHECK FIRST!
if self._mode_before_off:
    await self._restore_mode(st, transition)
    return  # MUST return - has absolute priority!

# Only if no saved mode:
await self._manual_control(st, brightness, temp, transition)
```

**Why?** Dashboard sends brightness parameter even on simple ON click. Without priority check, restore would be bypassed!

### 2. Context Tracking for Integration Updates
```python
# All PICO-internal state changes
self.async_write_ha_state(
    context=Context(id="picolightnode_restore")
)
```

**Why?** Keyframe Scheduler Blueprint needs to distinguish PICO-internal updates from real user actions.

### 3. follow_external is User Setting
```python
# ✅ ONLY set from HA entities
self._follow_external = True
st.follow_external = True

# ❌ NEVER set from MQTT handlers
# (It's a user preference, not PICO hardware state)
```

### 4. MQTT Override Messages
```python
# Disable override (no point data)
await publish_override_point(mqtt, topic, point=None, enabled=False)
# Sends: {"enabled": false}

# Enable with specific value
await publish_override_point(mqtt, topic, point, enabled=True)
# Sends: {"enabled": true, "point": {"brightness": 0.5, ...}}
```

**CRITICAL:** Follow External restore MUST send saved brightness, not just `enabled=true` (would use PICO defaultpoint!)

## Code Style
- Type hints everywhere
- RestoreEntity for persistent state
- async/await patterns
- Descriptive logging (no emoji in production)
- Clean separation: persistent vs. temporary state

## Testing Requirements
Before any commit:
1. Test Smart Restore (all three modes: follow, device, manual)
2. Test Follow External Switch behavior
3. Test Context Tracking (check logs for context.id)
4. Test integration with Keyframe Scheduler Blueprint
5. Verify MQTT payloads are correct

## The Three Automation Levels

### 🔵 Manual Override
User controls directly via Dashboard
- MQTT: `manual_override` enabled=true
- Follow External: OFF
- Smart Restore: mode_before_off = "manual"

### 🟢 Internal Automation
PICO firmware Daily Scheduler
- No MQTT needed (firmware-level)
- Follow External: OFF
- Smart Restore: mode_before_off = "device"

### 🟡 External Automation (Follow External)
Keyframe Scheduler controls via MQTT
- MQTT: `automation_override` enabled=true
- Follow External: ON
- Smart Restore: mode_before_off = "follow"

## Integration with Keyframe Scheduler

### How They Work Together
```
Keyframe Scheduler → Sensor (brightness, temp)
                           ↓
         Blueprint → light.turn_on service
                           ↓
         PICOlightnode → MQTT automation_override
                           ↓
              PICO Hardware → Physical light
```

### Context Tracking Enables
- Blueprint knows when PICO does Smart Restore
- No false manual override detection
- Follow External stays ON after restore
