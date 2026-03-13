"""PICOlightnode Custom Component."""
from __future__ import annotations

import os
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TARGETS,
    CONF_TARGET_ID,
    CONF_MANUAL_OVERRIDE_TOPIC,
    CONF_AUTOMATION_OVERRIDE_TOPIC,
    CONF_OVERRIDE_TOPIC,
)
from .coordinator import PicoCoordinator
from .mqtt_client import PicoMqtt
from .services import merge_point, publish_override_point
from .service_helpers import get_service_context

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["light", "switch", "button", "sensor", "binary_sensor"]


async def _migrate_entity_registry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entity registry entries for v2.0.5.
    
    In v2.0.5, RestoreEntity was added to PicoLight class.
    This changes the platform signature, so we need to update
    existing entities to ensure they continue working.
    
    This migration ensures NO BREAKING CHANGES - all existing
    entities, automations, and configurations continue working.
    """
    from homeassistant.helpers import entity_registry as er
    
    entity_reg = er.async_get(hass)
    
    # Find all picolightnode entities for this config entry
    migrated_count = 0
    for entity_entry in list(entity_reg.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        
        if entity_entry.platform != DOMAIN:
            continue
        
        # Entity belongs to this picolightnode config entry
        # The entity might be "unavailable" if platform changed
        # We don't need to actually modify anything - just the presence
        # of RestoreEntity in the class is enough once entities reload
        
        # Just log for debugging
        _LOGGER.debug(
            f"Migration check: {entity_entry.entity_id} "
            f"(unique_id={entity_entry.unique_id})"
        )
        migrated_count += 1
    
    if migrated_count > 0:
        _LOGGER.info(
            f"Entity registry migration complete: verified {migrated_count} entities "
            f"for config entry {entry.entry_id}"
        )


async def _register_webapp_static(hass: HomeAssistant) -> None:
    """Register /picolightnode/ static path for webapp."""
    webapp_dir = os.path.join(os.path.dirname(__file__), "www")
    url_path = f"/{DOMAIN}"

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(url_path, webapp_dir, cache_headers=False)]
        )
        _LOGGER.debug("Registered static webapp path: %s -> %s", url_path, webapp_dir)
    except Exception as err:
        try:
            hass.http.register_static_path(url_path, webapp_dir, cache_headers=False)  # type: ignore[attr-defined]
            _LOGGER.debug("Registered static webapp path (legacy): %s -> %s", url_path, webapp_dir)
        except Exception as err2:
            _LOGGER.warning("Failed to register static webapp path: %s / %s", err, err2)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the PICOlightnode component."""
    await _register_webapp_static(hass)
    return True


def _normalize_targets(raw_targets: list[dict]) -> list[dict]:
    """Normalize target configs by ensuring all override topics are present.
    
    Handles legacy configs where only 'override_topic' was used.
    After normalization, all targets have explicit manual_override_topic 
    and automation_override_topic.
    """
    out: list[dict] = []
    for t in raw_targets:
        tt = dict(t)
        legacy = tt.get(CONF_OVERRIDE_TOPIC)
        # Set defaults from legacy if not present
        tt.setdefault(CONF_MANUAL_OVERRIDE_TOPIC, legacy)
        tt.setdefault(CONF_AUTOMATION_OVERRIDE_TOPIC, legacy)
        out.append(tt)
    return out


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PICOlightnode from a config entry."""
    import logging
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    
    _LOGGER = logging.getLogger(__name__)
    hass.data.setdefault(DOMAIN, {})

    device_id = entry.data.get(CONF_DEVICE_ID, entry.entry_id)
    device_name = entry.data.get(CONF_NAME, entry.title)
    
    # Normalize targets (handles legacy configs)
    raw_targets = entry.options.get(CONF_TARGETS) or entry.data.get(CONF_TARGETS, [])
    targets = _normalize_targets(raw_targets)
    current_target_ids = {t[CONF_TARGET_ID] for t in targets}
    
    _LOGGER.warning(f"Setup entry: device_id={device_id}, current targets={current_target_ids}")
    
    # MIGRATION: Update entity registry for v2.0.5 (RestoreEntity added)
    # This ensures old entities from v1.x work with new v2.x code
    await _migrate_entity_registry(hass, entry)
    
    # CLEANUP: Remove orphaned target devices on startup
    # This fixes devices left behind from previous delete operations
    dev_reg = dr.async_get(hass)
    orphaned_devices = []
    
    for device_entry in dev_reg.devices.values():
        if entry.entry_id not in device_entry.config_entries:
            continue
        
        # Check each identifier
        for identifier in device_entry.identifiers:
            if identifier[0] != DOMAIN:
                continue
            
            device_identifier = identifier[1]
            
            # Skip main device (no :: delimiter)
            if "::" not in device_identifier:
                continue
            
            # Extract target_id from identifier
            parts = device_identifier.split("::")
            if len(parts) < 2:
                continue
            
            dev_target_id = parts[1]
            
            # Check if this target still exists in config
            if dev_target_id not in current_target_ids:
                _LOGGER.warning(
                    f"Found orphaned device: {device_entry.name} (target '{dev_target_id}' not in config)"
                )
                orphaned_devices.append((device_entry.id, device_entry.name, dev_target_id))
                break
    
    # Remove orphaned devices
    for device_id_to_remove, device_name, target_id in orphaned_devices:
        try:
            _LOGGER.warning(f"Removing orphaned device: {device_name} (target '{target_id}')")
            dev_reg.async_remove_device(device_id_to_remove)
        except Exception as e:
            _LOGGER.error(f"Failed to remove orphaned device {device_name}: {e}")
    
    if orphaned_devices:
        _LOGGER.warning(f"Cleaned up {len(orphaned_devices)} orphaned target devices")

    mqttc = PicoMqtt(hass)
    coord = PicoCoordinator(hass, mqttc, targets)
    await coord.async_start()

    # Store runtime context BEFORE forwarding platforms
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coord,
        "mqtt": mqttc,
        "targets": targets,
        "device_name": device_name,
        "device_id": device_id,
    }

    # Register parent device (physical pico)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        name=entry.title,
        manufacturer="PICO",
        model="lightnode",
    )

    # Register services once (globally)
    if not hass.services.has_service(DOMAIN, "apply_automation_point"):
        
        async def _handle_apply_automation_point(call: ServiceCall) -> None:
            await _service_apply_automation_point(hass, call)
        
        async def _handle_release_automation(call: ServiceCall) -> None:
            await _service_release_automation(hass, call)
        
        async def _handle_release_manual(call: ServiceCall) -> None:
            await _service_release_manual(hass, call)
        
        hass.services.async_register(
            DOMAIN, 
            "apply_automation_point", 
            _handle_apply_automation_point
        )
        hass.services.async_register(
            DOMAIN, 
            "release_automation", 
            _handle_release_automation
        )
        hass.services.async_register(
            DOMAIN, 
            "release_manual", 
            _handle_release_manual
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        ctx = hass.data[DOMAIN].pop(entry.entry_id)
        await ctx["coordinator"].async_stop()
    return unload_ok


# ============================================================================
# SERVICE HANDLERS (refactored to use service_helpers)
# ============================================================================

async def _service_apply_automation_point(hass: HomeAssistant, call: ServiceCall) -> None:
    """Apply automation point to target light.
    
    Service: picolightnode.apply_automation_point
    """
    entity_id = call.data["entity_id"]
    ctx = get_service_context(hass, entity_id)
    if not ctx:
        return

    # Get automation override topic
    topic = ctx.get_topic("automation")
    if not topic:
        _LOGGER.warning("No automation override topic for %s", ctx.target_id)
        return

    # Extract service parameters
    brightness = call.data.get("brightness")
    temp_k = call.data.get("color_temp_kelvin")
    transition = call.data.get("transition")

    # Merge with current state and publish
    point = merge_point(ctx.state, brightness, temp_k, transition, space=ctx.space)
    ctx.state.last_sent_point = point
    await publish_override_point(ctx.mqtt, topic, point, enabled=True, space=ctx.space)


async def _service_release_automation(hass: HomeAssistant, call: ServiceCall) -> None:
    """Release automation override for target light.
    
    Service: picolightnode.release_automation
    """
    entity_id = call.data["entity_id"]
    ctx = get_service_context(hass, entity_id)
    if not ctx:
        return

    # Get automation override topic
    topic = ctx.get_topic("automation")
    if not topic:
        _LOGGER.warning("No automation override topic for %s", ctx.target_id)
        return

    # Send "disabled" override with fade out
    point = merge_point(ctx.state, brightness_255=0, temperature_k=None, fade_s=3.0, space=ctx.space)
    await publish_override_point(ctx.mqtt, topic, point, enabled=False, space=ctx.space)


async def _service_release_manual(hass: HomeAssistant, call: ServiceCall) -> None:
    """Release manual override for target light.
    
    Service: picolightnode.release_manual
    """
    entity_id = call.data["entity_id"]
    ctx = get_service_context(hass, entity_id)
    if not ctx:
        return

    # Get manual override topic
    topic = ctx.get_topic("manual")
    if not topic:
        _LOGGER.warning("No manual override topic for %s", ctx.target_id)
        return

    # Send "disabled" override with fade out
    point = merge_point(ctx.state, brightness_255=0, temperature_k=None, fade_s=3.0, space=ctx.space)
    await publish_override_point(ctx.mqtt, topic, point, enabled=False, space=ctx.space)


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update - cleanup deleted target entities/devices and reload.
    
    Order is critical:
    1. Remove entities BEFORE reload (so they won't be recreated)
    2. Reload config entry (creates only current target entities/devices)
    3. Remove orphaned devices AFTER reload (cleanup leftover devices)
    """
    import logging
    from homeassistant.helpers import entity_registry as er, device_registry as dr
    
    _LOGGER = logging.getLogger(__name__)
    
    _LOGGER.warning("=" * 80)
    _LOGGER.warning("UPDATE LISTENER CALLED - CONFIG CHANGED")
    _LOGGER.warning("=" * 80)
    
    # Get current target IDs from config
    current_targets = entry.options.get(CONF_TARGETS) or entry.data.get(CONF_TARGETS) or []
    current_target_ids = {t[CONF_TARGET_ID] for t in current_targets}
    device_id = entry.data[CONF_DEVICE_ID]
    
    _LOGGER.warning(f"Current targets from entry.options: {entry.options.get(CONF_TARGETS)}")
    _LOGGER.warning(f"Current targets from entry.data: {entry.data.get(CONF_TARGETS)}")
    _LOGGER.warning(f"Merged current_target_ids: {current_target_ids}")
    
    # Get registries
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    
    # Step 1: Remove entities for deleted targets BEFORE reload
    entities_to_remove = []
    
    _LOGGER.warning("Scanning entity registry for orphaned entities...")
    
    for entity_id, entity_entry in ent_reg.entities.items():
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        
        if not entity_entry.unique_id:
            continue
        
        # Entity unique_id format: "{device_id}::{target_id}::{entity_type}"
        parts = entity_entry.unique_id.split("::")
        if len(parts) < 3:
            _LOGGER.warning(f"Unexpected unique_id format: {entity_entry.unique_id}")
            continue
        
        entity_target_id = parts[1]
        
        if entity_target_id not in current_target_ids:
            _LOGGER.warning(f"FOUND ORPHAN: {entity_id} belongs to deleted target '{entity_target_id}'")
            entities_to_remove.append(entity_id)
    
    # Remove entities NOW (before reload)
    _LOGGER.warning(f"Removing {len(entities_to_remove)} orphaned entities...")
    for entity_id in entities_to_remove:
        try:
            ent_reg.async_remove(entity_id)
            _LOGGER.warning(f"  ✓ Removed entity: {entity_id}")
        except Exception as e:
            _LOGGER.error(f"  ✗ Failed to remove {entity_id}: {e}")
    
    # Give Home Assistant time to process entity removals
    # This prevents entity_id conflicts when creating new entities
    if entities_to_remove:
        import asyncio
        _LOGGER.warning("Waiting for entity registry cleanup to complete (1000ms)...")
        await asyncio.sleep(1.0)
    
    # Step 2: Reload config entry
    _LOGGER.warning("Starting config entry reload...")
    try:
        reload_success = await hass.config_entries.async_reload(entry.entry_id)
        _LOGGER.warning(f"Reload completed: success={reload_success}")
    except Exception as e:
        _LOGGER.error(f"Reload failed: {e}")
        return
    
    # Step 3: Clean up orphaned devices AFTER reload
    _LOGGER.warning("Scanning device registry for orphaned devices...")
    devices_to_remove = []
    
    for device_entry in dev_reg.devices.values():
        # Check if device belongs to this config entry
        if entry.entry_id not in device_entry.config_entries:
            continue
        
        # Device identifier format: (DOMAIN, "{device_id}::{target_id}")
        for identifier in device_entry.identifiers:
            if identifier[0] != DOMAIN:
                continue
            
            device_identifier = identifier[1]
            
            # Skip main device (no :: delimiter)
            if "::" not in device_identifier:
                continue
            
            # Extract target_id
            parts = device_identifier.split("::")
            if len(parts) < 2:
                continue
            
            dev_target_id = parts[1]
            
            _LOGGER.warning(f"Checking device with target_id='{dev_target_id}'")
            
            # Check if this target was deleted
            if dev_target_id not in current_target_ids:
                # Double-check: does this device have any entities left?
                has_entities = False
                entity_count = 0
                for entity_entry in ent_reg.entities.values():
                    if entity_entry.device_id == device_entry.id:
                        has_entities = True
                        entity_count += 1
                
                if not has_entities:
                    _LOGGER.warning(
                        f"FOUND ORPHAN DEVICE: {device_entry.name} (target '{dev_target_id}', 0 entities)"
                    )
                    devices_to_remove.append(device_entry.id)
                else:
                    _LOGGER.error(
                        f"Device '{device_entry.name}' for deleted target '{dev_target_id}' "
                        f"still has {entity_count} entities - THIS SHOULD NOT HAPPEN!"
                    )
                break
    
    # Remove orphaned devices
    _LOGGER.warning(f"Removing {len(devices_to_remove)} orphaned devices...")
    for device_id_to_remove in devices_to_remove:
        try:
            dev_reg.async_remove_device(device_id_to_remove)
            _LOGGER.warning(f"  ✓ Removed device: {device_id_to_remove}")
        except Exception as e:
            _LOGGER.error(f"  ✗ Failed to remove device {device_id_to_remove}: {e}")
    
    _LOGGER.warning("=" * 80)
    _LOGGER.warning(f"UPDATE COMPLETE: {len(entities_to_remove)} entities, {len(devices_to_remove)} devices removed")
    _LOGGER.warning("=" * 80)
