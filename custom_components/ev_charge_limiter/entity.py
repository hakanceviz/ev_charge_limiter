"""Base entity for EV Charge Limiter."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CONF_NAME, DOMAIN, VERSION
from .manager import EvChargeLimiterManager


class EvChargeLimiterEntity(Entity):
    """Base EV Charge Limiter entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: EvChargeLimiterManager, key: str, name: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_name = name
        self._remove_listener: Callable[[], None] | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.manager.entry.entry_id)},
            name=self.manager.entry.data.get(CONF_NAME, "EV Charge Limiter"),
            manufacturer="Home Assistant Custom Integration",
            model="EV target charge helper",
            sw_version=VERSION,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.manager.snapshot
        return {
            "energy_sensor": self.manager.energy_sensor,
            "power_sensor": self.manager.power_sensor,
            "current_entity": self.manager.current_entity,
            "start_entity": self.manager.start_entity,
            "stop_entity": self.manager.stop_entity,
            "energy_mode": self.manager.energy_mode,
            "baseline_kwh": snapshot.data.get("baseline_kwh"),
            "last_stop_reason": snapshot.data.get("last_stop_reason"),
            "dynamic_buffer_kwh": snapshot.dynamic_buffer_kwh,
            "stop_threshold_kwh": snapshot.stop_threshold_kwh,
            "last_error": snapshot.data.get("last_error"),
            "stop_count": snapshot.data.get("stop_count", 0),
            "charger_maximum_current_a": snapshot.charger_max_current_a,
            "actual_charger_maximum_current_a": snapshot.actual_charger_max_current_a,
            "last_applied_current": snapshot.data.get("last_applied_current"),
        }

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self.manager.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None
