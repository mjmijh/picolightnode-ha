# PICOlightnode Architecture

## The Three Automation Levels

### 🔵 Level 1: Manual Override
**User controls directly via Dashboard**

- MQTT Topic: `{target}/override/manual`
- Priority: Highest
- Follow External Switch: OFF
- Smart Restore: mode_before_off = "manual"

**Code:**
```python
await publish_override_point(
    mqtt, manual_topic, point, enabled=True
)
self._manual_override_enabled = True
```

---

### 🟢 Level 2: Internal Automation (PICO Firmware)
**PICO Daily Scheduler runs independently**

- No MQTT needed (firmware-level)
- Works when HA offline
- Follow External Switch: OFF
- Smart Restore: mode_before_off = "device"

**Code (restore):**
```python
# Release both overrides → PICO takes over
await publish_override_point(mqtt, manual_topic, None, False)
await publish_override_point(mqtt, auto_topic, None, False)
```

---

### 🟡 Level 3: External Automation (Follow External)
**Keyframe Scheduler controls via MQTT**

- MQTT Topic: `{target}/override/automation`
- Continuous value updates from external source
- Follow External Switch: ON
- Smart Restore: mode_before_off = "follow"

**Code:**
```python
point = merge_point(st, brightness, temp, fade)
await publish_override_point(mqtt, auto_topic, point, True)
self._automation_override_enabled = True
```

---

## Component Structure
```
light_entity.py
├── PicoLight (RestoreEntity)
│   ├── async_turn_on()         # Entry point
│   ├── async_turn_off()        # Saves mode
│   ├── _restore_mode()         # Smart Restore
│   └── _manual_control()       # Direct control
│
switch_entity.py
├── PicoFollowExternalSwitch (RestoreEntity)
│   ├── async_turn_on()         # Enable Follow External
│   ├── async_turn_off()        # Disable Follow External
│   └── _handle_coordinator_update()  # Sync from coordinator
│
coordinator.py
└── PicoCoordinator
    ├── MQTT subscription
    └── State management (PicoTargetState)
```

---

## State Flow Diagram
```
User Dashboard Click
    ↓
light.turn_on(brightness=128)
    ↓
async_turn_on() called
    ↓
Check: self._mode_before_off?
    ├─ YES → _restore_mode()  [PRIORITY PATH]
    │           ↓
    │   Restore "follow"/"device"/"manual"
    │           ↓
    │   Set Context(id="picolightnode_restore")
    │
    └─ NO → _manual_control()
                ↓
        Send MQTT manual override
```

---

## Context Tracking System

### Why Context?
Keyframe Scheduler Blueprint needs to distinguish:
- ✅ TRUE user actions → Disable Follow External
- ❌ PICO-internal updates → Keep Follow External

### Implementation
```python
# In Smart Restore and MQTT updates
self.async_write_ha_state(
    context=Context(id="picolightnode_restore")
)
```

### Blueprint Detection
```yaml
{% set context_id = trigger.to_state.context.id | default('') %}
{% set from_pico = 'picolightnode' in context_id %}
{{ has_user and not has_parent and not from_pico }}
```

### Context Sources
| Source | user_id | parent_id | context.id | Manual Override? |
|--------|---------|-----------|------------|------------------|
| User Dashboard | ✅ | ❌ | (default) | YES |
| PICO Restore | ❌ | ❌ | picolightnode_restore | NO |
| Blueprint | ❌ | ✅ | (auto) | NO |