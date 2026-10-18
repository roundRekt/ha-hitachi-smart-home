"""Climate platform for ha-hitachi-smart-home."""

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

from . import HitachiConfigEntry
from .coordinator import Coordinator
from .const import (
    DOMAIN,
    KEY_CODE, KEY_NAME, KEY_HOME_ID, KEY_DEVICE_TYPE, KEY_XKQ_TYPE,
    KEY_STATE, KEY_TARGET_TEMP, KEY_MODE, KEY_CUR_TEMP,
    KEY_IS_XKQ, KEY_HALF_SUPPORT, KEY_INDOOR_HUMIDITY,
    CTRL_ONOFF, CTRL_TEMP, CTRL_MODE,
    DEVICE_TYPE_NAMES, DEVICE_TYPE_FRESH_AIR,
    MODE_OFF, MODE_COOL, MODE_DRY, MODE_FAN_ONLY, MODE_HEAT, MODE_AUTO,
    XKQ_CTRL_RUN, XKQ_CTRL_TEMP, XKQ_CTRL_ADD05,
    XKQ_MODE_CMD_MAP, XKQ_MODE_CMD_COOL,
)

_LOGGER = logging.getLogger(__name__)

# Mapping: API mode value -> HA HVACMode
HVAC_MODES = {
    MODE_OFF: HVACMode.OFF,
    MODE_COOL: HVACMode.COOL,
    MODE_HEAT: HVACMode.HEAT,
    MODE_AUTO: HVACMode.AUTO,
    MODE_DRY: HVACMode.DRY,
    MODE_FAN_ONLY: HVACMode.FAN_ONLY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitachiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    devices = coordinator.get_devices()
    entities = []
    for home_id, home_devices in devices.items():
        for xkq in home_devices["xkqList"]:
            entities.append(
                HitachiClimate(home_id, xkq[KEY_CODE], coordinator)
            )
    _LOGGER.debug("Adding %d climate entities", len(entities))
    async_add_entities(entities)


class HitachiClimate(CoordinatorEntity[Coordinator], ClimateEntity):
    """Climate entity for a single Hitachi indoor unit (Thermostat profile)."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator):
        super().__init__(coordinator)
        self._home_id = home_id
        self._xkq_code = xkq_code
        self._is_fresh_air = False
        self._is_xkq = False
        self._update_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self):
        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        if dev:
            # Device type detection
            device_type = dev.get(KEY_XKQ_TYPE, "")
            self._is_fresh_air = (device_type == DEVICE_TYPE_FRESH_AIR)
            self._is_xkq = dev.get(KEY_IS_XKQ, False)

            model_name = DEVICE_TYPE_NAMES.get(device_type)
            if not model_name:
                model_name = "智能线控器" if self._is_xkq else "中央空调室内机"

            self._attr_name = dev.get(KEY_NAME, f"Hitachi {self._xkq_code}")
            self._attr_unique_id = f"hitachi-{self._home_id}-{self._xkq_code}-climate"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"hitachi_{self._home_id}_{self._xkq_code}")},
                name=self._attr_name,
                manufacturer="Hisense Hitachi",
                model=model_name,
            )

            # Temperature limits & precision
            cold_min = dev.get("coldMin", 16)
            heat_min = dev.get("heatMin", 16)
            cold_max = dev.get("coldMax", 32)
            heat_max = dev.get("heatMax", 32)
            self._attr_min_temp = min(cold_min, heat_min)
            self._attr_max_temp = max(cold_max, heat_max)
            self._attr_target_temperature_step = 0.5 if dev.get(KEY_HALF_SUPPORT) else 1.0

            # Supported features: Target temperature, turn on, turn off (Fan mode removed)
            features = (
                ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
            )
            if not self._is_fresh_air:
                features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_supported_features = features

            self._attr_target_temperature = dev.get(KEY_TARGET_TEMP)
            self._attr_current_temperature = dev.get(KEY_CUR_TEMP)

            # Humidity reporting
            indoor_hum = dev.get(KEY_INDOOR_HUMIDITY, 0)
            self._attr_current_humidity = indoor_hum if indoor_hum > 0 else None

            # Primary on/off indicator
            onoff = dev.get(KEY_STATE, 0)
            if onoff == 0:
                self._attr_hvac_mode = HVACMode.OFF
            else:
                if self._is_fresh_air:
                    self._attr_hvac_mode = HVACMode.FAN_ONLY
                else:
                    mode = dev.get(KEY_MODE, MODE_COOL)
                    self._attr_hvac_mode = HVAC_MODES.get(mode, HVACMode.COOL)
        else:
            self._attr_target_temperature = None
            self._attr_current_temperature = None
            self._attr_current_humidity = None
            self._attr_hvac_mode = HVACMode.OFF

    @property
    def hvac_modes(self):
        if self._is_fresh_air:
            return [HVACMode.OFF, HVACMode.FAN_ONLY]
        return list(HVAC_MODES.values())

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac action for live HomeKit display."""
        if self._attr_hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._attr_hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        if self._attr_hvac_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if self._attr_hvac_mode == HVACMode.DRY:
            return HVACAction.DRYING
        if self._attr_hvac_mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        if self._attr_hvac_mode == HVACMode.AUTO:
            if self._attr_current_temperature is not None and self._attr_target_temperature is not None:
                if self._attr_current_temperature > self._attr_target_temperature:
                    return HVACAction.COOLING
                return HVACAction.HEATING
            return HVACAction.IDLE
        return None

    # ---- Control methods ----

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        last_mode = dev.get(KEY_MODE, MODE_COOL) if dev else MODE_COOL
        hvac_mode = HVAC_MODES.get(last_mode, HVACMode.COOL)
        if hvac_mode == HVACMode.OFF:
            hvac_mode = HVACMode.COOL
        await self.async_set_hvac_mode(hvac_mode)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs):
        # Handle hvac_mode if passed alongside temperature (e.g. from Siri or automations)
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)

        # Extract target temperature, supporting single target or range threshold fallback
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if self._attr_hvac_mode == HVACMode.HEAT and target_temp_low is not None:
                target_temp = target_temp_low
            elif self._attr_hvac_mode == HVACMode.COOL and target_temp_high is not None:
                target_temp = target_temp_high
            elif target_temp_high is not None and target_temp_low is not None:
                target_temp = round((target_temp_low + target_temp_high) / 2, 1)
            elif target_temp_high is not None:
                target_temp = target_temp_high
            elif target_temp_low is not None:
                target_temp = target_temp_low

        if target_temp is not None:
            if self._is_xkq:
                int_temp = int(target_temp)
                has_half = 1 if (round(target_temp * 2) % 2 == 1) else 0
                cmd = {XKQ_CTRL_TEMP: int_temp, XKQ_CTRL_ADD05: has_half}
            else:
                temp_val = round(target_temp * 2) / 2
                if temp_val.is_integer():
                    temp_val = int(temp_val)
                # Control API uses flat key "temp", not "iu31Temp"
                cmd = {CTRL_TEMP: temp_val}
            await self.coordinator.control(self._home_id, self._xkq_code, cmd)
            self._attr_target_temperature = target_temp
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.OFF:
            if self._is_xkq:
                cmd = {XKQ_CTRL_RUN: 0}
            else:
                cmd = {CTRL_ONOFF: 0}
            self._attr_hvac_mode = HVACMode.OFF
        else:
            if self._is_fresh_air:
                mode_key = MODE_FAN_ONLY
            else:
                mode_key = {v: k for k, v in HVAC_MODES.items()}.get(hvac_mode, MODE_COOL)

            if self._is_xkq:
                mode_cmd_field = XKQ_MODE_CMD_MAP.get(mode_key, XKQ_MODE_CMD_COOL)
                cmd = {XKQ_CTRL_RUN: 1, mode_cmd_field: 1}
            else:
                cmd = {CTRL_ONOFF: 1, CTRL_MODE: mode_key}
            self._attr_hvac_mode = hvac_mode
        await self.coordinator.control(self._home_id, self._xkq_code, cmd)
        self.async_write_ha_state()
