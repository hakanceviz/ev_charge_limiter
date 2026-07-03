"""Session manager for EV Charge Limiter."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CREATE_NOTIFICATION,
    CONF_CURRENT_ENTITY,
    CONF_ENERGY_MODE,
    CONF_ENERGY_SENSOR,
    CONF_POWER_SENSOR,
    CONF_START_ENTITY,
    CONF_START_SERVICE,
    CONF_STOP_ENTITY,
    CONF_STOP_SERVICE,
    DATA_APPLY_CURRENT_ON_START,
    DATA_BASELINE_KWH,
    DATA_BATTERY_CAPACITY,
    DATA_CHARGER_MAX_CURRENT,
    DATA_DYNAMIC_BUFFER_ENABLED,
    DATA_EARLY_STOP_BUFFER,
    DATA_EFFICIENCY,
    DATA_ENABLED,
    DATA_INTERVAL_ACCUMULATED_KWH,
    DATA_LAST_APPLIED_CURRENT,
    DATA_LAST_ERROR,
    DATA_LAST_STOP_REASON,
    DATA_SENSOR_LAG_SECONDS,
    DATA_START_CHARGER_ON_SESSION_START,
    DATA_START_SOC,
    DATA_STOP_COUNT,
    DATA_STOPPED,
    DATA_TARGET_SOC,
    DEFAULTS,
    DOMAIN,
    ENERGY_MODE_CUMULATIVE,
    ENERGY_MODE_INTERVAL,
    ENERGY_MODE_SESSION,
    STATUS_DISABLED,
    STATUS_ERROR,
    STATUS_MONITORING,
    STATUS_TARGET_REACHED,
    STATUS_WAITING_FOR_CURRENT,
    STATUS_WAITING_FOR_ENERGY,
    STATUS_WAITING_FOR_POWER,
    STOP_SERVICE_AUTO,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ManagerSnapshot:
    """Immutable-ish snapshot payload for entities."""

    data: dict[str, Any]
    delivered_kwh: float
    required_grid_kwh: float
    stop_threshold_kwh: float
    target_grid_kwh: float
    remaining_kwh: float
    remaining_to_full_target_kwh: float
    manual_buffer_kwh: float
    dynamic_buffer_kwh: float
    total_buffer_kwh: float
    current_power_kw: float | None
    charger_max_current_a: float
    actual_charger_max_current_a: float | None
    estimated_minutes_remaining: float | None
    estimated_finish_time: datetime | None
    estimated_soc: float | None
    status: str
    raw_energy_kwh: float | None


class EvChargeLimiterManager:
    """Manage one EV charge limiter config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.json"
        )
        self.data: dict[str, Any] = dict(DEFAULTS)
        self._listeners: list[Callable[[], None]] = []
        self._remove_state_listener: Callable[[], None] | None = None

    async def async_setup(self) -> None:
        """Load stored data and start listening to the energy/power sensors."""
        stored = await self._store.async_load()
        if stored:
            self.data.update(stored)
        # Bring older storage forward without losing user values.
        for key, value in DEFAULTS.items():
            self.data.setdefault(key, value)
        self._attach_state_listeners()
        self.async_notify_listeners()

    async def async_unload(self) -> None:
        """Unload listeners."""
        if self._remove_state_listener is not None:
            self._remove_state_listener()
            self._remove_state_listener = None
        self._listeners.clear()

    @property
    def config(self) -> dict[str, Any]:
        """Return config entry data merged with options."""
        merged = dict(self.entry.data)
        merged.update(self.entry.options)
        return merged

    @property
    def energy_sensor(self) -> str:
        return self.config[CONF_ENERGY_SENSOR]

    @property
    def power_sensor(self) -> str | None:
        value = self.config.get(CONF_POWER_SENSOR)
        return str(value).strip() if value else None

    @property
    def current_entity(self) -> str | None:
        value = self.config.get(CONF_CURRENT_ENTITY)
        return str(value).strip() if value else None

    @property
    def start_entity(self) -> str | None:
        value = self.config.get(CONF_START_ENTITY)
        if value:
            return str(value).strip()
        stop_entity = self.stop_entity
        domain = stop_entity.split(".", 1)[0]
        if domain in ("switch", "input_boolean"):
            return stop_entity
        return None

    @property
    def stop_entity(self) -> str:
        return self.config[CONF_STOP_ENTITY]

    @property
    def energy_mode(self) -> str:
        return self.config.get(CONF_ENERGY_MODE, ENERGY_MODE_SESSION)

    @property
    def create_notification(self) -> bool:
        return bool(self.config.get(CONF_CREATE_NOTIFICATION, True))

    def _attach_state_listeners(self) -> None:
        if self._remove_state_listener is not None:
            self._remove_state_listener()
        entity_ids = [self.energy_sensor]
        if self.power_sensor:
            entity_ids.append(self.power_sensor)
        if self.current_entity:
            entity_ids.append(self.current_entity)
        self._remove_state_listener = async_track_state_change_event(
            self.hass, entity_ids, self._async_state_changed
        )

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Add a listener for data changes."""
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove_listener

    @callback
    def async_notify_listeners(self) -> None:
        """Notify entities."""
        for listener in list(self._listeners):
            listener()

    async def _async_save(self) -> None:
        await self._store.async_save(self.data)

    async def async_set_value(self, key: str, value: float) -> None:
        """Set a numeric setting."""
        self.data[key] = float(value)
        self.data[DATA_LAST_ERROR] = ""
        await self._async_save()
        self.async_notify_listeners()
        if (
            key == DATA_CHARGER_MAX_CURRENT
            and self.data.get(DATA_ENABLED)
            and self.data.get(DATA_APPLY_CURRENT_ON_START, True)
            and self.current_entity
        ):
            await self._async_apply_charger_current()
        await self.async_evaluate()

    async def async_set_bool(self, key: str, value: bool) -> None:
        """Set a boolean setting."""
        self.data[key] = bool(value)
        self.data[DATA_LAST_ERROR] = ""
        await self._async_save()
        self.async_notify_listeners()
        await self.async_evaluate()

    async def async_start_session(self) -> None:
        """Capture a new baseline, optionally apply current, start the charger, and enable monitoring."""
        current = self.current_energy_kwh
        self.data[DATA_BASELINE_KWH] = current
        self.data[DATA_INTERVAL_ACCUMULATED_KWH] = 0.0
        self.data[DATA_ENABLED] = True
        self.data[DATA_STOPPED] = False
        self.data[DATA_LAST_STOP_REASON] = ""
        self.data[DATA_LAST_ERROR] = ""
        await self._async_save()
        self.async_notify_listeners()

        if self.data.get(DATA_APPLY_CURRENT_ON_START, True) and self.current_entity:
            ok = await self._async_apply_charger_current()
            if not ok:
                self.data[DATA_ENABLED] = False
                await self._async_save()
                self.async_notify_listeners()
                return

        if self.data.get(DATA_START_CHARGER_ON_SESSION_START, True):
            ok = await self._async_call_start_action()
            if not ok:
                self.data[DATA_ENABLED] = False
                await self._async_save()
                self.async_notify_listeners()
                return

        await self.async_evaluate()

    async def async_disable(self) -> None:
        """Disable monitoring without calling the charger stop entity."""
        self.data[DATA_ENABLED] = False
        self.data[DATA_LAST_ERROR] = ""
        await self._async_save()
        self.async_notify_listeners()

    async def async_stop_now(self, reason: str = "manual_stop") -> None:
        """Immediately call the configured charger stop action."""
        await self._async_call_stop_action(reason)

    @callback
    def _async_state_changed(self, event: Event) -> None:
        """Handle monitored entity state changes."""
        self.hass.async_create_task(self._async_handle_state_changed(event))

    async def _async_handle_state_changed(self, event: Event) -> None:
        """Process an energy/power state change."""
        entity_id = event.data.get("entity_id")
        if entity_id == self.energy_sensor and self.energy_mode == ENERGY_MODE_INTERVAL:
            await self._async_add_interval_energy(event.data.get("new_state"))
        await self.async_evaluate()

    async def _async_add_interval_energy(self, state: State | None) -> None:
        """Add an interval/delta energy reading to the session accumulator."""
        if not self.data.get(DATA_ENABLED):
            return
        value = self._state_to_kwh(state)
        if value is None or value < 0:
            return
        self.data[DATA_INTERVAL_ACCUMULATED_KWH] = float(
            self.data.get(DATA_INTERVAL_ACCUMULATED_KWH, 0.0)
        ) + value
        # Store on every interval update so a Home Assistant restart does not lose the session.
        await self._async_save()

    async def async_evaluate(self) -> None:
        """Stop charging when the delivered energy reaches the effective stop threshold."""
        if not self.data.get(DATA_ENABLED):
            self.async_notify_listeners()
            return

        required = self.required_grid_kwh
        threshold = self.stop_threshold_kwh
        delivered = self.delivered_kwh
        if required <= 0:
            self.data[DATA_LAST_ERROR] = "Target energy is zero. Check start/target SoC."
            self.async_notify_listeners()
            return

        if self.energy_mode != ENERGY_MODE_INTERVAL and self.current_energy_kwh is None:
            self.async_notify_listeners()
            return

        if delivered >= threshold:
            power_text = "unknown" if self.current_power_kw is None else f"{self.current_power_kw:.2f} kW"
            await self._async_call_stop_action(
                "Target reached: "
                f"delivered {delivered:.2f} kWh / stop threshold {threshold:.2f} kWh "
                f"/ required {required:.2f} kWh / live power {power_text}"
            )
        else:
            self.async_notify_listeners()


    async def _async_apply_charger_current(self) -> bool:
        """Apply the desired charger current to the configured current entity."""
        current_entity = self.current_entity
        if not current_entity:
            self.data[DATA_LAST_ERROR] = "Charger maximum current entity is not configured."
            await self._async_save()
            self.async_notify_listeners()
            return False

        target_current = max(0.0, float(self.data.get(DATA_CHARGER_MAX_CURRENT, 0.0)))
        if target_current <= 0:
            self.data[DATA_LAST_ERROR] = "Charger maximum current must be greater than 0 A."
            await self._async_save()
            self.async_notify_listeners()
            return False

        domain = current_entity.split(".", 1)[0]
        if domain not in ("number", "input_number"):
            self.data[DATA_LAST_ERROR] = f"Unsupported current entity domain: {domain}"
            await self._async_save()
            self.async_notify_listeners()
            return False

        try:
            await self.hass.services.async_call(
                domain,
                "set_value",
                {"entity_id": current_entity, "value": target_current},
                blocking=True,
            )
            self.data[DATA_LAST_APPLIED_CURRENT] = target_current
            self.data[DATA_LAST_ERROR] = ""
            await self._async_save()
            _LOGGER.info("EV charge limiter set charger maximum current to %.1f A", target_current)
            return True
        except Exception as err:  # noqa: BLE001 - surface the error in HA entity state
            _LOGGER.exception("Failed to set charger maximum current")
            self.data[DATA_LAST_ERROR] = f"Failed to set charger maximum current: {err}"
            await self._async_save()
            self.async_notify_listeners()
            return False

    async def _async_call_start_action(self) -> bool:
        """Call the configured start entity."""
        start_entity = self.start_entity
        if not start_entity:
            # Some chargers start automatically when plugged in. Treat no start entity as OK.
            return True

        domain = start_entity.split(".", 1)[0]
        service = self.config.get(CONF_START_SERVICE, STOP_SERVICE_AUTO)

        if service == STOP_SERVICE_AUTO:
            if domain in ("switch", "input_boolean", "light", "fan"):
                service_domain = domain
                service_name = "turn_on"
            elif domain == "button":
                service_domain = "button"
                service_name = "press"
            else:
                service_domain = "homeassistant"
                service_name = "turn_on"
        else:
            if "." not in service:
                self.data[DATA_LAST_ERROR] = f"Invalid start service: {service}"
                await self._async_save()
                self.async_notify_listeners()
                return False
            service_domain, service_name = service.split(".", 1)

        try:
            await self.hass.services.async_call(
                service_domain,
                service_name,
                {"entity_id": start_entity},
                blocking=True,
            )
            self.data[DATA_LAST_ERROR] = ""
            await self._async_save()
            _LOGGER.info("EV charge limiter started charger with %s.%s on %s", service_domain, service_name, start_entity)
            return True
        except Exception as err:  # noqa: BLE001 - surface the error in HA entity state
            _LOGGER.exception("Failed to start EV charger")
            self.data[DATA_LAST_ERROR] = f"Failed to start charger: {err}"
            await self._async_save()
            self.async_notify_listeners()
            return False

    async def _async_call_stop_action(self, reason: str) -> None:
        """Call the configured stop entity."""
        stop_entity = self.stop_entity
        domain = stop_entity.split(".", 1)[0]
        service = self.config.get(CONF_STOP_SERVICE, STOP_SERVICE_AUTO)

        if service == STOP_SERVICE_AUTO:
            if domain in ("switch", "input_boolean", "light", "fan"):
                service_domain = domain
                service_name = "turn_off"
            elif domain == "button":
                service_domain = "button"
                service_name = "press"
            else:
                service_domain = "homeassistant"
                service_name = "turn_off"
        else:
            if "." not in service:
                self.data[DATA_LAST_ERROR] = f"Invalid stop service: {service}"
                await self._async_save()
                self.async_notify_listeners()
                return
            service_domain, service_name = service.split(".", 1)

        try:
            await self.hass.services.async_call(
                service_domain,
                service_name,
                {"entity_id": stop_entity},
                blocking=True,
            )
            self.data[DATA_ENABLED] = False
            self.data[DATA_STOPPED] = True
            self.data[DATA_LAST_STOP_REASON] = reason
            self.data[DATA_LAST_ERROR] = ""
            self.data[DATA_STOP_COUNT] = int(self.data.get(DATA_STOP_COUNT, 0)) + 1
            await self._async_save()
            _LOGGER.info("EV charge limiter stopped charger: %s", reason)
            if self.create_notification:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "EV Charge Limiter",
                        "message": (
                            f"Şarj durduruldu. {reason}\n"
                            f"Verilen enerji: {self.delivered_kwh:.2f} kWh\n"
                            f"Gerekli enerji: {self.required_grid_kwh:.2f} kWh\n"
                            f"Kesme eşiği: {self.stop_threshold_kwh:.2f} kWh\n"
                            f"Anlık güç: {self.current_power_text}\n"
                            f"Maksimum akım: {self.charger_max_current_a:.1f} A\n"
                            f"Tahmini SoC: {self.estimated_soc_text}"
                        ),
                        "notification_id": f"{DOMAIN}_{self.entry.entry_id}_stopped",
                    },
                    blocking=False,
                )
        except Exception as err:  # noqa: BLE001 - surface the error in HA entity state
            _LOGGER.exception("Failed to stop EV charger")
            self.data[DATA_LAST_ERROR] = str(err)
            await self._async_save()
        finally:
            self.async_notify_listeners()

    @property
    def current_energy_kwh(self) -> float | None:
        """Return current value of the configured energy sensor as kWh."""
        state = self.hass.states.get(self.energy_sensor)
        return self._state_to_kwh(state)

    @staticmethod
    def _state_to_kwh(state: State | None) -> float | None:
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        unit = str(state.attributes.get("unit_of_measurement", "kWh")).strip()
        unit_lower = unit.lower()
        if unit == UnitOfEnergy.WATT_HOUR or unit_lower == "wh":
            return value / 1000.0
        if unit_lower == "mwh":
            return value * 1000.0
        return value

    @property
    def current_power_kw(self) -> float | None:
        """Return current value of the configured power sensor as kW."""
        power_sensor = self.power_sensor
        if not power_sensor:
            return None
        state = self.hass.states.get(power_sensor)
        return self._state_to_kw(state)

    @staticmethod
    def _state_to_kw(state: State | None) -> float | None:
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        unit = str(state.attributes.get("unit_of_measurement", "kW")).strip()
        unit_lower = unit.lower()
        if unit == UnitOfPower.WATT or unit_lower == "w":
            return value / 1000.0
        if unit_lower == "mw":
            return value * 1000.0
        return value

    @property
    def delivered_kwh(self) -> float:
        """Return delivered session energy in kWh."""
        if self.energy_mode == ENERGY_MODE_INTERVAL:
            return max(0.0, float(self.data.get(DATA_INTERVAL_ACCUMULATED_KWH, 0.0)))

        current = self.current_energy_kwh
        if current is None:
            return 0.0
        if self.energy_mode == ENERGY_MODE_CUMULATIVE:
            baseline = self.data.get(DATA_BASELINE_KWH)
            if baseline is None:
                return 0.0
            return max(0.0, current - float(baseline))
        return max(0.0, current)

    @property
    def required_grid_kwh(self) -> float:
        """Energy needed from the charger before any stop buffers."""
        capacity = float(self.data.get(DATA_BATTERY_CAPACITY, 0.0))
        start_soc = float(self.data.get(DATA_START_SOC, 0.0))
        target_soc = float(self.data.get(DATA_TARGET_SOC, 0.0))
        efficiency = float(self.data.get(DATA_EFFICIENCY, 90.0)) / 100.0
        soc_delta = max(0.0, target_soc - start_soc)
        if capacity <= 0 or efficiency <= 0 or soc_delta <= 0:
            return 0.0
        return (capacity * soc_delta / 100.0) / efficiency

    @property
    def manual_buffer_kwh(self) -> float:
        return max(0.0, float(self.data.get(DATA_EARLY_STOP_BUFFER, 0.0)))

    @property
    def dynamic_buffer_kwh(self) -> float:
        """Predictive buffer based on live kW and configured sensor lag."""
        if not bool(self.data.get(DATA_DYNAMIC_BUFFER_ENABLED, True)):
            return 0.0
        power_kw = self.current_power_kw
        if power_kw is None or power_kw <= 0:
            return 0.0
        lag_seconds = max(0.0, float(self.data.get(DATA_SENSOR_LAG_SECONDS, 0.0)))
        return max(0.0, power_kw * lag_seconds / 3600.0)

    @property
    def total_buffer_kwh(self) -> float:
        return self.manual_buffer_kwh + self.dynamic_buffer_kwh

    @property
    def stop_threshold_kwh(self) -> float:
        """Effective delivered energy at which charging should stop."""
        return max(0.0, self.required_grid_kwh - self.total_buffer_kwh)

    @property
    def target_grid_kwh(self) -> float:
        """Backward-compatible name for the effective stop threshold."""
        return self.stop_threshold_kwh

    @property
    def remaining_kwh(self) -> float:
        """Remaining kWh before the charger stop call should happen."""
        return max(0.0, self.stop_threshold_kwh - self.delivered_kwh)

    @property
    def remaining_to_full_target_kwh(self) -> float:
        """Remaining kWh to the unbuffered user target."""
        return max(0.0, self.required_grid_kwh - self.delivered_kwh)

    @property
    def estimated_minutes_remaining(self) -> float | None:
        power_kw = self.current_power_kw
        if power_kw is None or power_kw <= 0:
            return None
        return self.remaining_kwh / power_kw * 60.0

    @property
    def estimated_finish_time(self) -> datetime | None:
        minutes = self.estimated_minutes_remaining
        if minutes is None:
            return None
        return dt_util.now() + timedelta(minutes=minutes)

    @property
    def estimated_soc(self) -> float | None:
        capacity = float(self.data.get(DATA_BATTERY_CAPACITY, 0.0))
        efficiency = float(self.data.get(DATA_EFFICIENCY, 90.0)) / 100.0
        start_soc = float(self.data.get(DATA_START_SOC, 0.0))
        if capacity <= 0:
            return None
        soc = start_soc + (self.delivered_kwh * efficiency / capacity * 100.0)
        return max(0.0, min(100.0, soc))

    @property
    def estimated_soc_text(self) -> str:
        soc = self.estimated_soc
        return "unknown" if soc is None else f"{soc:.1f}%"

    @property
    def current_power_text(self) -> str:
        power = self.current_power_kw
        return "unknown" if power is None else f"{power:.2f} kW"

    @property
    def charger_max_current_a(self) -> float:
        return max(0.0, float(self.data.get(DATA_CHARGER_MAX_CURRENT, 0.0)))

    @property
    def actual_charger_max_current_a(self) -> float | None:
        current_entity = self.current_entity
        if not current_entity:
            return None
        state = self.hass.states.get(current_entity)
        return self._state_to_ampere(state)

    @staticmethod
    def _state_to_ampere(state: State | None) -> float | None:
        if state is None or state.state in ("unknown", "unavailable", ""):
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        unit = str(state.attributes.get("unit_of_measurement", "A")).strip().lower()
        if unit in ("ma", "milliampere", "milliamps"):
            return value / 1000.0
        return value

    @property
    def status(self) -> str:
        if self.data.get(DATA_LAST_ERROR):
            return STATUS_ERROR
        if self.data.get(DATA_STOPPED):
            return STATUS_TARGET_REACHED
        if self.data.get(DATA_ENABLED):
            if self.energy_mode != ENERGY_MODE_INTERVAL and self.current_energy_kwh is None:
                return STATUS_WAITING_FOR_ENERGY
            if self.power_sensor and self.current_power_kw is None:
                return STATUS_WAITING_FOR_POWER
            if self.current_entity and self.actual_charger_max_current_a is None:
                return STATUS_WAITING_FOR_CURRENT
            return STATUS_MONITORING
        return STATUS_DISABLED

    @property
    def snapshot(self) -> ManagerSnapshot:
        estimated_minutes = self.estimated_minutes_remaining
        return ManagerSnapshot(
            data=dict(self.data),
            delivered_kwh=round(self.delivered_kwh, 3),
            required_grid_kwh=round(self.required_grid_kwh, 3),
            stop_threshold_kwh=round(self.stop_threshold_kwh, 3),
            target_grid_kwh=round(self.target_grid_kwh, 3),
            remaining_kwh=round(self.remaining_kwh, 3),
            remaining_to_full_target_kwh=round(self.remaining_to_full_target_kwh, 3),
            manual_buffer_kwh=round(self.manual_buffer_kwh, 3),
            dynamic_buffer_kwh=round(self.dynamic_buffer_kwh, 3),
            total_buffer_kwh=round(self.total_buffer_kwh, 3),
            current_power_kw=(None if self.current_power_kw is None else round(self.current_power_kw, 3)),
            charger_max_current_a=round(self.charger_max_current_a, 1),
            actual_charger_max_current_a=(
                None if self.actual_charger_max_current_a is None else round(self.actual_charger_max_current_a, 1)
            ),
            estimated_minutes_remaining=(
                None if estimated_minutes is None else round(estimated_minutes, 1)
            ),
            estimated_finish_time=self.estimated_finish_time,
            estimated_soc=(None if self.estimated_soc is None else round(self.estimated_soc, 1)),
            status=self.status,
            raw_energy_kwh=self.current_energy_kwh,
        )
