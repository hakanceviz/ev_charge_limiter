"""Config flow for EV Charge Limiter."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_CREATE_NOTIFICATION,
    CONF_CURRENT_ENTITY,
    CONF_ENERGY_MODE,
    CONF_ENERGY_SENSOR,
    CONF_NAME,
    CONF_POWER_SENSOR,
    CONF_START_ENTITY,
    CONF_START_SERVICE,
    CONF_STOP_ENTITY,
    CONF_STOP_SERVICE,
    DOMAIN,
    ENERGY_MODE_CUMULATIVE,
    ENERGY_MODE_INTERVAL,
    ENERGY_MODE_SESSION,
    STOP_SERVICE_AUTO,
)


def _friendly_text(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    name = state.attributes.get("friendly_name", entity_id) if state else entity_id
    return f"{entity_id} {name}".lower()


def _guess_energy_sensor(hass: HomeAssistant) -> str | None:
    """Try to find a likely OCPP energy sensor."""
    preferred_tokens = [
        "energy active import register",
        "energy_active_import_register",
        "energy active import interval",
        "energy_active_import_interval",
        "energy active import",
        "energy session",
        "ocpp",
    ]
    candidates: list[tuple[int, str]] = []
    for state in hass.states.async_all("sensor"):
        text = _friendly_text(hass, state.entity_id)
        unit = str(state.attributes.get("unit_of_measurement", "")).lower()
        if unit not in ("kwh", "wh", "mwh"):
            continue
        score = sum(2 if token in text and "ocpp" in token else 1 for token in preferred_tokens if token in text)
        if "energy active import register" in text or "energy_active_import_register" in text:
            score += 5
        if score:
            candidates.append((score, state.entity_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][1]


def _guess_power_sensor(hass: HomeAssistant) -> str | None:
    """Try to find a likely OCPP live power sensor."""
    preferred_tokens = [
        "power active import",
        "power_active_import",
        "active power",
        "charging power",
        "charger power",
        "ocpp",
    ]
    candidates: list[tuple[int, str]] = []
    for state in hass.states.async_all("sensor"):
        text = _friendly_text(hass, state.entity_id)
        unit = str(state.attributes.get("unit_of_measurement", "")).lower()
        if unit not in ("kw", "w", "mw"):
            continue
        score = sum(1 for token in preferred_tokens if token in text)
        if "power active import" in text or "power_active_import" in text:
            score += 5
        if score:
            candidates.append((score, state.entity_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][1]


def _guess_current_entity(hass: HomeAssistant) -> str | None:
    """Try to find a likely OCPP maximum current number entity."""
    preferred_tokens = [
        "charger maximum current",
        "charger_maximum_current",
        "maximum current",
        "max current",
        "charging current",
        "current limit",
        "ocpp",
    ]
    candidates: list[tuple[int, str]] = []
    for domain in ("number", "input_number"):
        for state in hass.states.async_all(domain):
            text = _friendly_text(hass, state.entity_id)
            unit = str(state.attributes.get("unit_of_measurement", "")).lower()
            if unit not in ("a", "amp", "amps", "ampere", "amper"):
                continue
            score = sum(1 for token in preferred_tokens if token in text)
            if "charger maximum current" in text or "charger_maximum_current" in text:
                score += 8
            if "maximum current" in text or "max current" in text:
                score += 4
            if score:
                candidates.append((score, state.entity_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][1]


def _guess_start_entity(hass: HomeAssistant, stop_entity: str | None = None) -> str | None:
    """Try to find a likely entity that starts/enables charging."""
    if stop_entity:
        domain = stop_entity.split(".", 1)[0]
        if domain in ("switch", "input_boolean"):
            return stop_entity
    preferred_tokens = [
        "charge control",
        "charge_control",
        "start charging",
        "start_charge",
        "charging control",
        "ocpp",
        "charger",
    ]
    candidates: list[tuple[int, str]] = []
    for domain in ("switch", "button", "input_boolean"):
        for state in hass.states.async_all(domain):
            text = _friendly_text(hass, state.entity_id)
            score = sum(1 for token in preferred_tokens if token in text)
            if "charge control" in text or "charge_control" in text:
                score += 5
            if "start" in text:
                score += 3
            if score:
                candidates.append((score, state.entity_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][1]


def _guess_stop_entity(hass: HomeAssistant) -> str | None:
    """Try to find a likely OCPP charge control entity."""
    preferred_tokens = [
        "charge control",
        "charge_control",
        "charging control",
        "ocpp",
        "charger",
    ]
    candidates: list[tuple[int, str]] = []
    for domain in ("switch", "button", "input_boolean"):
        for state in hass.states.async_all(domain):
            text = _friendly_text(hass, state.entity_id)
            score = sum(1 for token in preferred_tokens if token in text)
            if "charge control" in text or "charge_control" in text:
                score += 5
            if score:
                candidates.append((score, state.entity_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][1]


def _with_default(required_or_optional: Any, key: str, guessed: str | None) -> Any:
    if guessed:
        return required_or_optional(key, default=guessed)
    return required_or_optional(key)


def _schema(hass: HomeAssistant, defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    guessed_energy = defaults.get(CONF_ENERGY_SENSOR) or _guess_energy_sensor(hass)
    guessed_power = defaults.get(CONF_POWER_SENSOR) or _guess_power_sensor(hass)
    guessed_current = defaults.get(CONF_CURRENT_ENTITY) or _guess_current_entity(hass)
    guessed_stop = defaults.get(CONF_STOP_ENTITY) or _guess_stop_entity(hass)
    guessed_start = defaults.get(CONF_START_ENTITY) or _guess_start_entity(hass, guessed_stop)

    energy_key = _with_default(vol.Required, CONF_ENERGY_SENSOR, guessed_energy)
    stop_key = _with_default(vol.Required, CONF_STOP_ENTITY, guessed_stop)
    power_key = _with_default(vol.Optional, CONF_POWER_SENSOR, guessed_power)
    current_key = _with_default(vol.Optional, CONF_CURRENT_ENTITY, guessed_current)
    start_key = _with_default(vol.Optional, CONF_START_ENTITY, guessed_start)

    fields: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "EV Charge Limiter")): str,
        energy_key: selector({"entity": {"domain": "sensor"}}),
        power_key: selector({"entity": {"domain": "sensor"}}),
        current_key: selector({"entity": {"domain": ["number", "input_number"]}}),
        start_key: selector({"entity": {"domain": ["switch", "button", "input_boolean"]}}),
        stop_key: selector({"entity": {"domain": ["switch", "button", "input_boolean"]}}),
        vol.Required(CONF_ENERGY_MODE, default=defaults.get(CONF_ENERGY_MODE, ENERGY_MODE_SESSION)): selector(
            {
                "select": {
                    "options": [
                        {
                            "value": ENERGY_MODE_SESSION,
                            "label": "Session register: sensor resets to 0 at each charge",
                        },
                        {
                            "value": ENERGY_MODE_CUMULATIVE,
                            "label": "Cumulative meter: use baseline when session starts",
                        },
                        {
                            "value": ENERGY_MODE_INTERVAL,
                            "label": "Interval delta: every update is an energy delta and will be summed",
                        },
                    ],
                    "mode": "dropdown",
                }
            }
        ),
        vol.Optional(CONF_START_SERVICE, default=defaults.get(CONF_START_SERVICE, STOP_SERVICE_AUTO)): str,
        vol.Optional(CONF_STOP_SERVICE, default=defaults.get(CONF_STOP_SERVICE, STOP_SERVICE_AUTO)): str,
        vol.Required(CONF_CREATE_NOTIFICATION, default=defaults.get(CONF_CREATE_NOTIFICATION, True)): selector({"boolean": {}}),
    }
    return vol.Schema(fields)


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_STOP_SERVICE] = (data.get(CONF_STOP_SERVICE) or STOP_SERVICE_AUTO).strip() or STOP_SERVICE_AUTO
    data[CONF_START_SERVICE] = (data.get(CONF_START_SERVICE) or STOP_SERVICE_AUTO).strip() or STOP_SERVICE_AUTO
    data[CONF_POWER_SENSOR] = (data.get(CONF_POWER_SENSOR) or "").strip()
    data[CONF_CURRENT_ENTITY] = (data.get(CONF_CURRENT_ENTITY) or "").strip()
    data[CONF_START_ENTITY] = (data.get(CONF_START_ENTITY) or "").strip()
    return data


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    energy_sensor = user_input.get(CONF_ENERGY_SENSOR)
    power_sensor = user_input.get(CONF_POWER_SENSOR)
    current_entity = user_input.get(CONF_CURRENT_ENTITY)
    start_entity = user_input.get(CONF_START_ENTITY)
    stop_entity = user_input.get(CONF_STOP_ENTITY)

    if energy_sensor == stop_entity:
        errors[CONF_STOP_ENTITY] = "same_entity"
    if power_sensor and power_sensor == energy_sensor:
        errors[CONF_POWER_SENSOR] = "same_power_energy"
    if power_sensor and power_sensor == stop_entity:
        errors[CONF_POWER_SENSOR] = "same_power_stop"
    if current_entity and current_entity in (energy_sensor, power_sensor, stop_entity, start_entity):
        errors[CONF_CURRENT_ENTITY] = "same_current_other"
    return errors


class EvChargeLimiterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EV Charge Limiter."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Create the options flow."""
        return EvChargeLimiterOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = _normalize_input(user_input)
            errors = _validate(user_input)

            if not errors:
                unique_id = f"{user_input[CONF_ENERGY_SENSOR]}_{user_input[CONF_STOP_ENTITY]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "EV Charge Limiter"),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass),
            errors=errors,
        )


class EvChargeLimiterOptionsFlow(config_entries.OptionsFlow):
    """Handle EV Charge Limiter options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        base = dict(self._config_entry.data)
        base.update(self._config_entry.options)
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _normalize_input(user_input)
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(self.hass, base),
            errors=errors,
        )
