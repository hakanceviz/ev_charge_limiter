"""Constants for EV Charge Limiter."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "ev_charge_limiter"
NAME: Final = "EV Charge Limiter"
VERSION: Final = "0.2.0"

PLATFORMS: Final = ["sensor", "number", "switch", "button"]

CONF_NAME: Final = "name"
CONF_ENERGY_SENSOR: Final = "energy_sensor"
CONF_POWER_SENSOR: Final = "power_sensor"
CONF_STOP_ENTITY: Final = "stop_entity"
CONF_ENERGY_MODE: Final = "energy_mode"
CONF_STOP_SERVICE: Final = "stop_service"
CONF_CREATE_NOTIFICATION: Final = "create_notification"

ENERGY_MODE_SESSION: Final = "session_register"
ENERGY_MODE_CUMULATIVE: Final = "cumulative_meter"
ENERGY_MODE_INTERVAL: Final = "interval_delta"
ENERGY_MODES: Final = [ENERGY_MODE_SESSION, ENERGY_MODE_CUMULATIVE, ENERGY_MODE_INTERVAL]

STOP_SERVICE_AUTO: Final = "auto"

DATA_BATTERY_CAPACITY: Final = "battery_capacity_kwh"
DATA_START_SOC: Final = "start_soc_percent"
DATA_TARGET_SOC: Final = "target_soc_percent"
DATA_EFFICIENCY: Final = "efficiency_percent"
DATA_EARLY_STOP_BUFFER: Final = "early_stop_buffer_kwh"
DATA_DYNAMIC_BUFFER_ENABLED: Final = "dynamic_buffer_enabled"
DATA_SENSOR_LAG_SECONDS: Final = "sensor_lag_seconds"
DATA_ENABLED: Final = "enabled"
DATA_BASELINE_KWH: Final = "baseline_kwh"
DATA_INTERVAL_ACCUMULATED_KWH: Final = "interval_accumulated_kwh"
DATA_STOPPED: Final = "stopped"
DATA_LAST_STOP_REASON: Final = "last_stop_reason"
DATA_LAST_ERROR: Final = "last_error"
DATA_STOP_COUNT: Final = "stop_count"

DEFAULTS: Final = {
    DATA_BATTERY_CAPACITY: 60.0,
    DATA_START_SOC: 20.0,
    DATA_TARGET_SOC: 80.0,
    DATA_EFFICIENCY: 90.0,
    DATA_EARLY_STOP_BUFFER: 0.10,
    DATA_DYNAMIC_BUFFER_ENABLED: True,
    DATA_SENSOR_LAG_SECONDS: 60.0,
    DATA_ENABLED: False,
    DATA_BASELINE_KWH: None,
    DATA_INTERVAL_ACCUMULATED_KWH: 0.0,
    DATA_STOPPED: False,
    DATA_LAST_STOP_REASON: "",
    DATA_LAST_ERROR: "",
    DATA_STOP_COUNT: 0,
}

STATUS_DISABLED: Final = "disabled"
STATUS_MONITORING: Final = "monitoring"
STATUS_TARGET_REACHED: Final = "target_reached"
STATUS_ERROR: Final = "error"
STATUS_WAITING_FOR_ENERGY: Final = "waiting_for_energy"
STATUS_WAITING_FOR_POWER: Final = "waiting_for_power"
