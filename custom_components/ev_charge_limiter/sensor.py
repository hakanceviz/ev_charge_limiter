"""Sensor entities for EV Charge Limiter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EvChargeLimiterEntity
from .manager import EvChargeLimiterManager


@dataclass(frozen=True, kw_only=True)
class EvSensorDescription(SensorEntityDescription):
    """Describe an EV Charge Limiter sensor."""

    value_key: str


SENSORS: tuple[EvSensorDescription, ...] = (
    EvSensorDescription(
        key="status",
        name="Status",
        value_key="status",
    ),
    EvSensorDescription(
        key="required_grid_energy",
        name="Required Grid Energy",
        value_key="required_grid_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    EvSensorDescription(
        key="stop_threshold_energy",
        name="Stop Threshold Energy",
        value_key="stop_threshold_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    # Backward-compatible entity for v0.1.x users. It now mirrors the effective stop threshold.
    EvSensorDescription(
        key="target_grid_energy",
        name="Target Grid Energy",
        value_key="target_grid_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    EvSensorDescription(
        key="delivered_energy",
        name="Delivered Energy",
        value_key="delivered_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    EvSensorDescription(
        key="remaining_energy",
        name="Remaining Energy To Stop",
        value_key="remaining_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    EvSensorDescription(
        key="remaining_energy_to_full_target",
        name="Remaining Energy To Target",
        value_key="remaining_to_full_target_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    EvSensorDescription(
        key="manual_buffer",
        name="Manual Stop Buffer",
        value_key="manual_buffer_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    EvSensorDescription(
        key="dynamic_buffer",
        name="Dynamic Power Buffer",
        value_key="dynamic_buffer_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    EvSensorDescription(
        key="total_buffer",
        name="Total Stop Buffer",
        value_key="total_buffer_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    EvSensorDescription(
        key="charger_maximum_current",
        name="Charger Maximum Current",
        value_key="charger_max_current_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    EvSensorDescription(
        key="actual_charger_maximum_current",
        name="Actual Charger Maximum Current",
        value_key="actual_charger_max_current_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    EvSensorDescription(
        key="current_power",
        name="Current Charging Power",
        value_key="current_power_kw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    EvSensorDescription(
        key="estimated_minutes_remaining",
        name="Estimated Time Remaining",
        value_key="estimated_minutes_remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    EvSensorDescription(
        key="estimated_finish_time",
        name="Estimated Finish Time",
        value_key="estimated_finish_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    EvSensorDescription(
        key="estimated_soc",
        name="Estimated SoC",
        value_key="estimated_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    EvSensorDescription(
        key="raw_energy",
        name="Raw Charger Energy",
        value_key="raw_energy_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    manager: EvChargeLimiterManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EvChargeLimiterSensor(manager, description) for description in SENSORS)


class EvChargeLimiterSensor(EvChargeLimiterEntity, SensorEntity):
    """EV Charge Limiter sensor."""

    entity_description: EvSensorDescription

    def __init__(self, manager: EvChargeLimiterManager, description: EvSensorDescription) -> None:
        super().__init__(manager, description.key, description.name or description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        snapshot = self.manager.snapshot
        return getattr(snapshot, self.entity_description.value_key)
