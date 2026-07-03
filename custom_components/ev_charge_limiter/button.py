"""Button entities for EV Charge Limiter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EvChargeLimiterEntity
from .manager import EvChargeLimiterManager


@dataclass(frozen=True, kw_only=True)
class EvButtonDescription(ButtonEntityDescription):
    """Describe an EV Charge Limiter button."""

    action: str


BUTTONS: tuple[EvButtonDescription, ...] = (
    EvButtonDescription(
        key="start_session",
        name="Start New Session",
        action="start_session",
    ),
    EvButtonDescription(
        key="stop_now",
        name="Stop Charge Now",
        action="stop_now",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    manager: EvChargeLimiterManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EvChargeLimiterButton(manager, description) for description in BUTTONS)


class EvChargeLimiterButton(EvChargeLimiterEntity, ButtonEntity):
    """EV Charge Limiter button."""

    entity_description: EvButtonDescription

    def __init__(self, manager: EvChargeLimiterManager, description: EvButtonDescription) -> None:
        super().__init__(manager, description.key, description.name or description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        if self.entity_description.action == "start_session":
            await self.manager.async_start_session()
        elif self.entity_description.action == "stop_now":
            await self.manager.async_stop_now("manual_button_stop")
