# PICOlightnode v2 Development Instructions

## Project Type
Home Assistant Custom Integration for PICO Lighting Hardware (MQTT-based)

## Current Version
v2.0.18 - Context Tracking + Smart Restore

## Development Focus
- Maintain Context Tracking system
- Smart Restore has absolute priority
- Follow External is User Setting (HA-only)
- Integration with Keyframe Scheduler Blueprint

## Key Principles
1. PICO-internal updates MUST use Context(id="picolightnode_restore")
2. mode_before_off checked BEFORE any other logic
3. follow_external never set from MQTT handlers
4. Follow External restore sends saved brightness as initial value

## Code Style
- Type hints everywhere
- Descriptive logging (no debug emojis in production)
- RestoreEntity for persistent state
- async/await patterns

## Testing Requirements
Before any commit:
1. Test Smart Restore (all three modes)
2. Test Follow External Switch behavior
3. Check Context IDs in logs
4. Verify Blueprint integration