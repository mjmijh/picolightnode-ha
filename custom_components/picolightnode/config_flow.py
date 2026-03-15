from __future__ import annotations

import logging
import re
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TARGETS,
    CONF_TARGET_ID,
    CONF_TARGET_NAME,
    CONF_TARGET_SPACE,
    CONF_STATE_TOPIC,
    CONF_MIN_KELVIN,
    CONF_MAX_KELVIN,
    CONF_MANUAL_OVERRIDE_TOPIC,
    CONF_AUTOMATION_OVERRIDE_TOPIC,
    SPACE_TC,
    SPACE_BRIGHTNESS,
)


def _slugify(value: str) -> str:
    value = value.strip().lower().replace("/", "_")
    value = re.sub(r"[^a-z0-9_\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "target"


class PicoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._device: dict = {}
        self._targets: list[dict] = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._device = user_input
            return await self.async_step_target()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="PICOlightnode"): str,
                vol.Required(CONF_DEVICE_ID, default="pico_1"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_target(self, user_input=None) -> FlowResult:
        if user_input is not None:
            tid = user_input.get(CONF_TARGET_ID) or _slugify(user_input[CONF_TARGET_NAME])

            self._targets.append(
                {
                    CONF_TARGET_ID: tid,
                    CONF_TARGET_NAME: user_input[CONF_TARGET_NAME],
                    CONF_TARGET_SPACE: user_input.get(CONF_TARGET_SPACE, SPACE_TC),
                    CONF_STATE_TOPIC: user_input[CONF_STATE_TOPIC],
                    CONF_MANUAL_OVERRIDE_TOPIC: user_input[CONF_MANUAL_OVERRIDE_TOPIC],
                    CONF_AUTOMATION_OVERRIDE_TOPIC: user_input[CONF_AUTOMATION_OVERRIDE_TOPIC],
                    CONF_MIN_KELVIN: user_input.get(CONF_MIN_KELVIN, 2700),
                    CONF_MAX_KELVIN: user_input.get(CONF_MAX_KELVIN, 5700),
                }
            )
            return await self.async_step_add_more()

        schema = vol.Schema(
            {
                vol.Optional(CONF_TARGET_NAME, default=f"Target {len(self._targets)+1}"): str,
                vol.Optional(CONF_TARGET_ID): str,
                vol.Required(
                    CONF_TARGET_SPACE,
                    default=SPACE_TC
                ): vol.In({
                    SPACE_TC: "Tunable White (with Kelvin control)",
                    SPACE_BRIGHTNESS: "Brightness only (Kelvin fields ignored)",
                }),
                vol.Required(CONF_STATE_TOPIC): str,
                vol.Required(CONF_MANUAL_OVERRIDE_TOPIC): str,
                vol.Required(CONF_AUTOMATION_OVERRIDE_TOPIC): str,
                vol.Optional(CONF_MIN_KELVIN, default=2700): vol.Coerce(int),
                vol.Optional(CONF_MAX_KELVIN, default=5700): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="target", data_schema=schema)

    async def async_step_add_more(self, user_input=None) -> FlowResult:
        # Ask right after each target whether to add another one
        if user_input is not None:
            if user_input.get('add_more') == 'yes':
                return await self.async_step_target()
            return await self.async_step_finish()

        schema = vol.Schema({vol.Required('add_more', default='yes'): vol.In({'yes': 'Add another target', 'no': 'Done'})})
        return self.async_show_form(step_id='add_more', data_schema=schema)

    async def async_step_finish(self, user_input=None) -> FlowResult:
        if len(self._targets) == 0:
            return await self.async_step_target()

        data = {**self._device, CONF_TARGETS: self._targets}
        return self.async_create_entry(title=self._device[CONF_NAME], data=data)


    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return PicoOptionsFlow(config_entry)


class PicoOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._targets: list[dict] = []
        self._selected: str | None = None
        self._editing: bool = False

    async def async_step_init(self, user_input=None) -> FlowResult:
        # Load current targets from entry (prefer options over data)
        self._targets = list(
            self._entry.options.get(CONF_TARGETS) or self._entry.data.get(CONF_TARGETS) or []
        )
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None) -> FlowResult:
        """Main menu - add, edit, or remove targets."""
        if user_input is not None:
            choice = user_input.get("menu")
            if choice == "add_target":
                self._editing = False
                self._selected = None
                return await self.async_step_target()
            if choice == "edit_target":
                return await self.async_step_pick_target_edit()
            if choice == "remove_target":
                return await self.async_step_pick_target_remove()
            if choice == "done":
                # Just exit - no explicit save needed
                return self.async_create_entry(title="", data={})

        options = {"add_target": "Add target"}
        if len(self._targets) > 0:
            options["edit_target"] = "Edit target"
            options["remove_target"] = "Remove target"
        options["done"] = "Done"

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema({vol.Required("menu"): vol.In(options)}),
            description_placeholders={
                "count": str(len(self._targets)),
                "targets": ", ".join(t.get(CONF_TARGET_NAME, t[CONF_TARGET_ID]) for t in self._targets) if self._targets else "None"
            },
        )

    async def async_step_pick_target_edit(self, user_input=None) -> FlowResult:
        """Pick which target to edit."""
        if user_input is not None:
            self._selected = user_input["target"]
            self._editing = True
            return await self.async_step_target()

        choices = {
            t[CONF_TARGET_ID]: t.get(CONF_TARGET_NAME, t[CONF_TARGET_ID]) 
            for t in self._targets
        }
        return self.async_show_form(
            step_id="pick_target_edit",
            data_schema=vol.Schema({vol.Required("target"): vol.In(choices)}),
        )

    async def async_step_pick_target_remove(self, user_input=None) -> FlowResult:
        """Pick which target to remove."""
        if user_input is not None:
            self._selected = user_input["target"]
            return await self.async_step_remove_confirm()

        choices = {
            t[CONF_TARGET_ID]: t.get(CONF_TARGET_NAME, t[CONF_TARGET_ID])
            for t in self._targets
        }
        return self.async_show_form(
            step_id="pick_target_remove",
            data_schema=vol.Schema({vol.Required("target"): vol.In(choices)}),
        )

    async def async_step_remove_confirm(self, user_input=None) -> FlowResult:
        """Confirm deletion and save immediately."""
        if user_input is not None:
            if user_input.get("confirm"):
                # Remove target
                self._targets = [t for t in self._targets if t[CONF_TARGET_ID] != self._selected]
                
                # Save immediately
                return self.async_create_entry(
                    title="", 
                    data={CONF_TARGETS: self._targets}
                )
            else:
                # User cancelled - back to menu
                self._selected = None
                return await self.async_step_menu()

        # Show confirmation
        target_name = "Unknown"
        for t in self._targets:
            if t[CONF_TARGET_ID] == self._selected:
                target_name = t.get(CONF_TARGET_NAME, self._selected)
                break

        return self.async_show_form(
            step_id="remove_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"target_name": target_name},
        )

    async def async_step_target(self, user_input=None) -> FlowResult:
        """Add or edit a target - saves immediately."""
        # Prefill if editing
        defaults: dict = {}
        if self._editing and self._selected:
            for t in self._targets:
                if t[CONF_TARGET_ID] == self._selected:
                    defaults = dict(t)
                    break

        if user_input is not None:
            # Preserve old ID when editing and field is empty
            old_tid = None
            if self._editing and self._selected:
                old_tid = self._selected
            
            # Generate or use provided ID
            tid_in = (user_input.get(CONF_TARGET_ID) or "").strip()
            if tid_in:
                tid = _slugify(tid_in)
            elif old_tid:
                # Editing: keep old ID (ID field not shown when editing)
                tid = old_tid
            else:
                # New: generate from name
                tid = _slugify(user_input[CONF_TARGET_NAME])

            # Create new target entry
            new_t = {
                CONF_TARGET_ID: tid,
                CONF_TARGET_NAME: user_input[CONF_TARGET_NAME].strip(),
                CONF_TARGET_SPACE: user_input.get(CONF_TARGET_SPACE, SPACE_TC),
                CONF_STATE_TOPIC: user_input[CONF_STATE_TOPIC].strip(),
                CONF_MANUAL_OVERRIDE_TOPIC: user_input[CONF_MANUAL_OVERRIDE_TOPIC].strip(),
                CONF_AUTOMATION_OVERRIDE_TOPIC: (
                    user_input.get(CONF_AUTOMATION_OVERRIDE_TOPIC) or ""
                ).strip(),
                CONF_MIN_KELVIN: int(user_input.get(CONF_MIN_KELVIN, 2700)),
                CONF_MAX_KELVIN: int(user_input.get(CONF_MAX_KELVIN, 5700)),
            }

            # If editing, remove old target first (with original ID)
            if self._editing and self._selected:
                self._targets = [t for t in self._targets if t[CONF_TARGET_ID] != self._selected]
                self._editing = False
                self._selected = None

            # Remove any duplicate IDs (safety check)
            self._targets = [t for t in self._targets if t[CONF_TARGET_ID] != tid]
            
            # Add new target
            self._targets.append(new_t)
            
            # Save and trigger reload
            # Note: We return async_create_entry which will trigger the update_listener
            # The update_listener will handle entity/device cleanup
            return self.async_create_entry(
                title="",
                data={CONF_TARGETS: self._targets}
            )

        # Show form
        # Build schema
        schema_dict = {}
        
        # ID field: Read-only when editing, editable when adding
        if self._editing:
            # When editing: Show current ID as disabled text field + warning
            current_id = defaults.get(CONF_TARGET_ID, 'N/A')
            
            # Log info: target ID cannot be changed via config flow
            _LOGGER.info(
                "Editing target '%s': ID cannot be changed here. "
                "To rename entity IDs go to Settings → Devices & Services → Entities.",
                current_id,
            )
        else:
            # When adding: Allow ID input
            schema_dict[vol.Optional(
                CONF_TARGET_ID, 
                default=defaults.get(CONF_TARGET_ID, "")
            )] = str
        
        # Name field
        schema_dict[vol.Required(
            CONF_TARGET_NAME, 
            default=defaults.get(CONF_TARGET_NAME, "")
        )] = str
        
        # Rest of schema
        schema_dict[vol.Required(
            CONF_TARGET_SPACE,
            default=defaults.get(CONF_TARGET_SPACE, SPACE_TC)
        )] = vol.In({
            SPACE_TC: "Tunable White (with Kelvin control)",
            SPACE_BRIGHTNESS: "Brightness only (Kelvin fields ignored)",
        })
        schema_dict[vol.Required(
            CONF_STATE_TOPIC, 
            default=defaults.get(CONF_STATE_TOPIC, "")
        )] = str
        schema_dict[vol.Required(
            CONF_MANUAL_OVERRIDE_TOPIC,
            default=defaults.get(CONF_MANUAL_OVERRIDE_TOPIC, ""),
        )] = str
        schema_dict[vol.Optional(
            CONF_AUTOMATION_OVERRIDE_TOPIC,
            default=defaults.get(CONF_AUTOMATION_OVERRIDE_TOPIC, ""),
        )] = str
        schema_dict[vol.Optional(
            CONF_MIN_KELVIN, 
            default=int(defaults.get(CONF_MIN_KELVIN, 2700))
        )] = int
        schema_dict[vol.Optional(
            CONF_MAX_KELVIN, 
            default=int(defaults.get(CONF_MAX_KELVIN, 5700))
        )] = int
        
        return self.async_show_form(
            step_id="target",
            data_schema=vol.Schema(schema_dict),
        )

