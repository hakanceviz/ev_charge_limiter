"""EV Charge Limiter integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_START_SOC,
    DOMAIN,
    PLATFORMS,
)
from .manager import EvChargeLimiterManager

_LOGGER = logging.getLogger(__name__)

SERVICE_START_SESSION = "start_session"
SERVICE_STOP_NOW = "stop_now"
SERVICE_SET_START_SOC = "set_start_soc"

SERVICE_ENTRY_SCHEMA = vol.Schema({vol.Optional("entry_id"): cv.string})
SERVICE_SET_START_SOC_SCHEMA = SERVICE_ENTRY_SCHEMA.extend(
    {vol.Required("start_soc"): vol.Coerce(float)}
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-wide services."""
    hass.data.setdefault(DOMAIN, {})

    async def _manager_from_call(call: ServiceCall) -> EvChargeLimiterManager | None:
        entry_id = call.data.get("entry_id")
        managers: dict[str, EvChargeLimiterManager] = hass.data.get(DOMAIN, {})
        if entry_id:
            manager = managers.get(entry_id)
            if manager is None:
                _LOGGER.warning("No EV Charge Limiter entry found for entry_id=%s", entry_id)
            return manager
        if len(managers) == 1:
            return next(iter(managers.values()))
        _LOGGER.warning("entry_id is required when more than one EV Charge Limiter entry exists")
        return None

    async def _handle_start_session(call: ServiceCall) -> None:
        manager = await _manager_from_call(call)
        if manager:
            await manager.async_start_session()

    async def _handle_stop_now(call: ServiceCall) -> None:
        manager = await _manager_from_call(call)
        if manager:
            await manager.async_stop_now("manual_service_stop")

    async def _handle_set_start_soc(call: ServiceCall) -> None:
        manager = await _manager_from_call(call)
        if manager:
            await manager.async_set_value(DATA_START_SOC, call.data["start_soc"])
            await manager.async_start_session()

    if not hass.services.has_service(DOMAIN, SERVICE_START_SESSION):
        hass.services.async_register(
            DOMAIN, SERVICE_START_SESSION, _handle_start_session, schema=SERVICE_ENTRY_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_STOP_NOW, _handle_stop_now, schema=SERVICE_ENTRY_SCHEMA
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_START_SOC,
            _handle_set_start_soc,
            schema=SERVICE_SET_START_SOC_SCHEMA,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EV Charge Limiter from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    manager = EvChargeLimiterManager(hass, entry)
    await manager.async_setup()
    hass.data[DOMAIN][entry.entry_id] = manager

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    manager: EvChargeLimiterManager | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if manager:
        await manager.async_unload()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry after options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)
