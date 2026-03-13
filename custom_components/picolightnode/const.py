DOMAIN = "picolightnode"

# Target Space Types (PICO Color Spaces)
SPACE_TC = "TC"  # Tunable Color (Brightness + Kelvin)
SPACE_BRIGHTNESS = "BRIGHTNESS"  # Brightness only
SPACE_RGB = "RGB"  # Future: RGB support

CONF_DEVICE_ID = "device_id"
CONF_NAME = "name"
CONF_TARGETS = "targets"
CONF_TARGET_ID = "id"
CONF_TARGET_NAME = "name"
CONF_TARGET_SPACE = "space"  # NEW: Color space type
CONF_STATE_TOPIC = "state_topic"
CONF_OVERRIDE_TOPIC = "override_topic"
CONF_MIN_KELVIN = "min_kelvin"
CONF_MAX_KELVIN = "max_kelvin"

DEFAULT_TEMP_K = 2700
DEFAULT_FADE_S = 0.0

ATTR_OVERRIDE_ENABLED = "override_enabled"
ATTR_FOLLOW_EXTERNAL = "follow_external_automation"
ATTR_CONTROL_MODE = "control_mode"

CONF_MANUAL_OVERRIDE_TOPIC = "manual_override_topic"
CONF_AUTOMATION_OVERRIDE_TOPIC = "automation_override_topic"

ATTR_MANUAL_OVERRIDE_ENABLED = "manual_override_enabled"
ATTR_AUTOMATION_OVERRIDE_ENABLED = "automation_override_enabled"
