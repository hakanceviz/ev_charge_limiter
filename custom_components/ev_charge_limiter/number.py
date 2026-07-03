"""Number entities for EV Charge Limiter."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_BATTERY_CAPACITY,
    DATA_EARLY_STOP_BUFFER,
    DATA_EFFICIENCY,
    DATA_SENSOR_LAG_SECONDS,
    DATA_START_SOC,
    DATA_TARGET_SOC,
    DOMAIN,
)
from .entity import EvChargeLimiterEntity
from .manager import EvChargeLimiterManager


@dataclass(frozen=True, kw_only=True)
class EvNumberDescription(NumberEntityDescription):
    """Describe an EV Charge Limiter number."""

    data_key: str


NUMBERS: tuple[EvNumberDescription, ...] = (
    EvNumberDescription(
        key="battery_capacity",
        name="Battery Capacity",
        data_key=DATA_BATTERY_CAPACITY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_min_value=10,
        native_max_value=200,
        native_step=0.1,
        mode=NumberMode.BOX,
    ),
    EvNumberDescription(
        key="start_soc",
        name="Start SoC",
        data_key=DATA_START_SOC,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    EvNumberDescription(
        key="target_soc",
        name="Target SoC",
        data_key=DATA_TARGET_SOC,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    EvNumberDescription(
        key="charging_efficiency",
        name="Charging Efficiency",
        data_key=DATA_EFFICIENCY,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=70,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
    EvNumberDescription(
        key="early_stop_buffer",
        name="Manual Early Stop Buffer",
        data_key=DATA_EARLY_STOP_BUFFER,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_min_value=0,
        native_max_value=5,
        native_step=0.05,
        mode=NumberMode.BOX,
    ),
    EvNumberDescription(
        key="sensor_lag_seconds",
        name="Power Sensor Lag",
        data_key=DATA_SENSOR_LAG_SECONDS,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=600,
        native_step=5,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    manager: EvChargeLimiterManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EvChargeLimiterNumber(manager, description) for description in NUMBERS)


class EvChargeLimiterNumber(EvChargeLimiterEntity, NumberEntity):
    """EV Charge Limiter number entity."""

    entity_description: EvNumberDescription

    def __init__(self, manager: EvChargeLimiterManager, description: EvNumberDescription) -> None:
        super().__init__(manager, description.key, description.name or description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        value = self.manager.data.get(self.entity_description.data_key)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        await self.manager.async_set_value(self.entity_description.data_key, float(value))
