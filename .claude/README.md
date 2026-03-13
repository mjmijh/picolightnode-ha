# PICOlightnode - Claude Code Context

This `.claude/` directory contains development context for Claude Code (AI coding assistant).

## 📁 Structure

```
.claude/
├── instructions.md              # High-level development instructions
├── architecture.md             # System architecture (compact)
├── PICO_KEYFRAME_CONCEPT.md    # Complete architecture documentation
├── rules.md                    # Code patterns and rules
├── examples/
│   ├── smart-restore.py        # Smart Restore implementation
│   └── blueprint-context.py    # Context detection examples
└── README.md                   # This file
```

## 🎯 Purpose

These files are **automatically loaded** by Claude Code and provide context for:
- Understanding Smart Restore architecture
- Following Context Tracking patterns
- Avoiding common bugs
- Maintaining PICO-Keyframe integration

## 📖 Quick Reference

### For Smart Restore Work
1. Read `rules.md` → Smart Restore Priority pattern
2. Check `examples/smart-restore.py` → Complete implementation
3. Review `architecture.md` → Data flow

### For Context Tracking
1. Check `rules.md` → Context on State Changes
2. See `examples/blueprint-context.py` → All context sources
3. Understand why it's needed: PICO_KEYFRAME_CONCEPT.md

### For Bug Fixes
1. Check `rules.md` → Common Bugs section
2. Review examples for correct patterns
3. Test against patterns in smart-restore.py

## 🚀 Using with Claude Code

When you chat with Claude Code:
- Claude automatically knows Smart Restore architecture
- Claude follows Context Tracking patterns
- Claude references examples when suggesting code

**Example prompts:**
```
"Add support for color mode in Smart Restore"
→ Claude will reference smart-restore.py and maintain patterns

"Fix the Context ID for button entities"
→ Claude will reference rules.md Context Tracking section

"Update Follow External Switch to sync better"
→ Claude will follow architecture.md structure
```

## 📦 What's NOT Here

❌ Secrets/API Keys (use `.env`)
❌ Generated code
❌ Build artifacts
❌ Very large files

## 🔄 Keeping Updated

When you make architectural changes:
1. Update relevant `.claude/*.md` files
2. Update examples in `.claude/examples/`
3. Keep consistent with actual code

Think of `.claude/` as **living documentation** that Claude uses.

## 🤝 Integration with Keyframe Scheduler

This PICOlightnode works closely with Keyframe Scheduler v3.0.10+:
- PICO sends `Context(id="picolightnode_restore")` on internal updates
- Keyframe Blueprint v4.0 detects this context
- Manual override detection works correctly

See `examples/blueprint-context.py` for full explanation.

## 📚 Related Documentation

- **Complete Architecture**: `PICO_KEYFRAME_CONCEPT.md` (in this directory)
- **README**: `README.md` (project root)
- **Keyframe Integration**: See Keyframe Scheduler `.claude/` setup

## 🎯 Critical Patterns

### Smart Restore Priority
```python
if self._mode_before_off:  # CHECK FIRST!
    await self._restore_mode(st, transition)
    return  # MUST return!
```

### Context Tracking
```python
self.async_write_ha_state(
    context=Context(id="picolightnode_restore")
)
```

### MQTT Override
```python
# Follow External restore - WITH saved brightness!
point = merge_point(st, brightness_before_off, temp_before_off, 0.0)
await publish_override_point(mqtt, auto_topic, point, enabled=True)
```

### Config Constant
```python
# CORRECT
from .const import CONF_AUTOMATION_OVERRIDE_TOPIC
automation_topic = self._target.get(CONF_AUTOMATION_OVERRIDE_TOPIC)
```

## 🐛 Common Bug Reminders

1. ❌ Smart Restore bypassed → Check priority in async_turn_on
2. ❌ Follow External disabled after restore → Check Context ID
3. ❌ automation_override_topic not found → Check CONF constant
4. ❌ Light goes to defaultpoint → Check point parameter

See `rules.md` for full bug list and solutions.

---

**Version**: v2.0.18
**Last Updated**: 2026-03-13
**Claude Code**: Compatible with all versions
