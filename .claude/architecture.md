# PICOlightnode Architecture

For complete architecture documentation, see: `PICO_KEYFRAME_CONCEPT.md` in this directory.

## Quick Component Overview

```
PICOlightnode Integration
├── Light Entity (RestoreEntity)
│   ├── async_turn_on()  → Smart Restore or Manual Control
│   ├── async_turn_off() → Save mode_before_off
│   ├── _restore_mode()  → Restore to follow/device/manual
│   └── _manual_control() → Direct brightness control
│
├── Follow External Switch (RestoreEntity)
│   ├── async_turn_on()  → Enable automation override
│   ├── async_turn_off() → Disable automation override
│   └── _handle_coordinator_update() → Sync from coordinator
│
├── Button Entities
│   ├── Manual Override Reset
│   ├── Automation Override Reset
│   └── All Overrides Reset
│
└── Coordinator
    ├── MQTT subscription → State updates
    └── PicoTargetState management
```

## Data Flow - Smart Restore

```
┌─────────────────────────┐
│  User: Light OFF        │
│  (Dashboard)            │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  async_turn_off()       │
│  ├─ Save current mode   │
│  │   - follow           │
│  │   - device           │
│  │   - manual           │
│  ├─ Save brightness     │
│  └─ Send MQTT OFF       │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  User: Light ON         │
│  (Dashboard)            │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  async_turn_on()        │
│  ├─ CHECK: mode_before  │
│  │   _off exists?       │
│  └─ YES → _restore_mode │
│      NO → _manual_ctrl  │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  _restore_mode()        │
│  ├─ mode="follow"       │
│  │   → Enable auto      │
│  │     override with    │
│  │     saved brightness │
│  │   → Set context ID   │
│  │                      │
│  ├─ mode="device"       │
│  │   → Disable both     │
│  │     overrides        │
│  │   → PICO takes over  │
│  │                      │
│  └─ mode="manual"       │
│      → Enable manual    │
│        override with    │
│        saved brightness │
└─────────────────────────┘
```

## MQTT Override Topics

```
{target}/override/manual
├─ Priority: Highest
├─ Payload: {"enabled": true/false, "point": {...}}
└─ Use: User manual control

{target}/override/automation
├─ Priority: Medium
├─ Payload: {"enabled": true/false, "point": {...}}
└─ Use: External automation (Keyframe Scheduler)
```

**PICO Firmware Priority:**
```
manual_override (enabled) → Highest
    ↓ (disabled)
automation_override (enabled) → Medium
    ↓ (disabled)
Internal Automation → Lowest
```

## Context Tracking Flow

```
┌────────────────────────────────────┐
│  Smart Restore triggered           │
│  (User clicked Light ON)           │
└─────────────┬──────────────────────┘
              ↓
┌────────────────────────────────────┐
│  _restore_mode()                   │
│  ├─ Send MQTT override             │
│  ├─ Update coordinator state       │
│  └─ async_write_ha_state(          │
│       context=Context(             │
│         id="picolightnode_restore" │
│       )                            │
│     )                              │
└─────────────┬──────────────────────┘
              ↓
┌────────────────────────────────────┐
│  State change in HA                │
│  context.id = "picolightnode_      │
│                restore"            │
└─────────────┬──────────────────────┘
              ↓
┌────────────────────────────────────┐
│  Keyframe Blueprint detects        │
│  {% set from_pico =                │
│      'picolightnode' in            │
│      context_id %}                 │
│  → from_pico = True                │
│  → NOT manual override             │
│  → Keep Follow External ON         │
└────────────────────────────────────┘
```

## Persistent State (RestoreEntity)

### Light Entity
```python
self._mode_before_off: str | None
    # "follow" | "device" | "manual"

self._brightness_before_off: int | None
    # 0-255

self._temperature_before_off: int | None
    # Kelvin

self._follow_external: bool
    # Follow External active?

self._manual_override_enabled: bool
    # Manual override active?

self._automation_override_enabled: bool
    # Automation override active?
```

### Follow External Switch
```python
self._follow_external: bool
    # Synced from coordinator
    # Source of truth for is_on property
```

## Key File Locations

```
custom_components/picolightnode/
├── light.py              # Setup light entities
├── light_entity.py       # PicoLight class (Smart Restore here!)
├── switch_entity.py      # PicoFollowExternalSwitch
├── button_entity.py      # Reset buttons
├── coordinator.py        # MQTT + State management
├── services.py           # publish_override_point()
├── const.py              # CONF_AUTOMATION_OVERRIDE_TOPIC
└── __init__.py           # Integration setup + migration
```

## Critical Functions

### publish_override_point
```python
async def publish_override_point(
    mqttc,
    override_topic,
    point: PicoPointTC | None,  # None = no point!
    enabled: bool,
    space=SPACE_TC
) -> None:
    """
    Send MQTT override message.
    
    point=None, enabled=False:
        {"enabled": false}
    
    point=None, enabled=True:
        {"enabled": true}
        → PICO uses defaultpoint!
    
    point=value, enabled=True:
        {"enabled": true, "point": {"brightness": 0.5, ...}}
    """
```

### Smart Restore Entry Point
```python
async def async_turn_on(self, **kwargs) -> None:
    """Turn on light with Smart Restore priority."""
    brightness = kwargs.get(ATTR_BRIGHTNESS)
    transition = kwargs.get(ATTR_TRANSITION)
    
    # CRITICAL: Check mode_before_off FIRST!
    if self._mode_before_off:
        await self._restore_mode(st, transition)
        return  # Don't proceed!
    
    # No saved mode → manual control
    await self._manual_control(st, brightness, temp, transition)
```

## Common Patterns

### Disable Both Overrides (→ Internal Auto)
```python
await publish_override_point(mqtt, manual_topic, None, False)
await publish_override_point(mqtt, auto_topic, None, False)
# PICO internal automation takes over
```

### Enable Follow External with Saved Brightness
```python
point = merge_point(st, brightness_before_off, temp_before_off, 0.0)
await publish_override_point(mqtt, manual_topic, None, False)
await publish_override_point(mqtt, auto_topic, point, True)
self.async_write_ha_state(context=Context(id="picolightnode_restore"))
```

### Enable Manual with Brightness
```python
point = merge_point(st, brightness, temp, transition, space)
await publish_override_point(mqtt, manual_topic, point, True)
```

## MQTT Payload Examples

### Disable Manual Override
```json
{
  "enabled": false
}
```

### Enable Manual Override with Brightness
```json
{
  "enabled": true,
  "point": {
    "brightness": 0.75,
    "temperature": 3500,
    "fade": 2.0
  }
}
```

### Enable Automation Override (Follow External Restore)
```json
{
  "enabled": true,
  "point": {
    "brightness": 1.0,
    "temperature": 4000,
    "fade": 0.0
  }
}
```

**Note:** Sending `{"enabled": true}` WITHOUT point makes PICO use `defaultpoint` from `setup.json`!

---

For detailed workflows, troubleshooting, and integration patterns, see `PICO_KEYFRAME_CONCEPT.md`.
