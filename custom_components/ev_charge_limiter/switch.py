"""Switch entities for EV Charge Limiter."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_DYNAMIC_BUFFER_ENABLED, DATA_ENABLED, DOMAIN
from .entity import EvChargeLimiterEntity
from .manager import EvChargeLimiterManager


@dataclass(frozen=True, kw_only=True)
class EvSwitchDescription(SwitchEntityDescription):
    """Describe an EV Charge Limiter switch."""

    data_key: str | None = None
    starts_session: bool = False


SWITCHES: tuple[EvSwitchDescription, ...] = (
    EvSwitchDescription(
        key="auto_stop_enabled",
        name="Auto Stop Enabled",
        data_key=DATA_ENABLED,
        starts_session=True,
    ),
    EvSwitchDescription(
        key="dynamic_power_buffer_enabled",
        name="Dynamic Power Buffer Enabled",
        data_key=DATA_DYNAMIC_BUFFER_ENABLED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    manager: EvChargeLimiterManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EvChargeLimiterSwitch(manager, description) for description in SWITCHES)


class EvChargeLimiterSwitch(EvChargeLimiterEntity, SwitchEntity):
    """EV Charge Limiter switch."""

    entity_description: EvSwitchDescription

    def __init__(self, manager: EvChargeLimiterManager, description: EvSwitchDescription) -> None:
        super().__init__(manager, description.key, description.name or description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        if self.entity_description.data_key is None:
            return False
        return bool(self.manager.data.get(self.entity_description.data_key))

    async def async_turn_on(self, **kwargs) -> None:
        if self.entity_description.starts_session:
            await self.manager.async_start_session()
            return
        if self.entity_description.data_key is not None:
            await self.manager.async_set_bool(self.entity_description.data_key, True)

    async def async_turn_off(self, **kwargs) -> None:
        if self.entity_description.starts_session:
            await self.manager.async_disable()
            return
        if self.entity_description.data_key is not None:
            await self.manager.async_set_bool(self.entity_description.data_key, False)
