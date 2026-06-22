"""Climate platform for ha-hatachi."""

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from . import HitachiConfigEntry
from .coordinator import Coordinator
from .const import (
    DOMAIN,
    KEY_CODE, KEY_NAME, KEY_HOME_ID, KEY_DEVICE_TYPE, KEY_XKQ_TYPE,
    KEY_STATE, KEY_TARGET_TEMP, KEY_MODE, KEY_FAN_SPEED, KEY_CUR_TEMP,
    CTRL_ONOFF, CTRL_TEMP, CTRL_MODE, CTRL_WIND,
    DEVICE_TYPE_NAMES, DEVICE_TYPE_FRESH_AIR,
    MODE_OFF, MODE_COOL, MODE_DRY, MODE_FAN_ONLY, MODE_HEAT,
    FAN_LOW, FAN_MEDIUM, FAN_HIGH,
)

_LOGGER = logging.getLogger(__name__)

# Mapping: API mode value -> HA HVACMode
HVAC_MODES = {
    MODE_OFF: HVACMode.OFF,
    MODE_COOL: HVACMode.COOL,
    MODE_DRY: HVACMode.DRY,
    MODE_FAN_ONLY: HVACMode.FAN_ONLY,
    MODE_HEAT: HVACMode.HEAT,
}

# Mapping: API fan value -> HA fan mode string
FAN_MODES = {
    FAN_LOW: "low",
    FAN_MEDIUM: "medium",
    FAN_HIGH: "high",
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
    """Climate entity for a single Hisense Hitachi indoor unit."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator):
        super().__init__(coordinator)
        self._home_id = home_id
        self._xkq_code = xkq_code
        self._is_fresh_air = False
        self._update_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self):
        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        if dev:
            # Device type detection (use xkqType = API iuType, not deviceType which is always "1")
            device_type = dev.get(KEY_XKQ_TYPE, "")
            self._is_fresh_air = (device_type == DEVICE_TYPE_FRESH_AIR)

            self._attr_name = dev.get(KEY_NAME, f"Hitachi {self._xkq_code}")
            self._attr_unique_id = f"hitachi-{self._home_id}-{self._xkq_code}-climate"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"hitachi_{self._home_id}_{self._xkq_code}")},
                name=self._attr_name,
                manufacturer="Hisense Hitachi",
                model=DEVICE_TYPE_NAMES.get(device_type, "未知"),
            )

            # Supported features: fresh air has no temperature control
            if self._is_fresh_air:
                self._attr_supported_features = ClimateEntityFeature.FAN_MODE
            else:
                self._attr_supported_features = (
                    ClimateEntityFeature.TARGET_TEMPERATURE
                    | ClimateEntityFeature.FAN_MODE
                )

            self._attr_target_temperature = dev.get(KEY_TARGET_TEMP)
            self._attr_current_temperature = dev.get(KEY_CUR_TEMP)

            # ---- KEY FIX: use iu28Onoff (KEY_STATE) as primary on/off indicator ----
            onoff = dev.get(KEY_STATE, 0)
            if onoff == 0:
                self._attr_hvac_mode = HVACMode.OFF
            else:
                if self._is_fresh_air:
                    # Fresh air only has FAN_ONLY when on
                    self._attr_hvac_mode = HVACMode.FAN_ONLY
                else:
                    mode = dev.get(KEY_MODE, MODE_COOL)
                    self._attr_hvac_mode = HVAC_MODES.get(mode, HVACMode.COOL)

            self._attr_fan_mode = FAN_MODES.get(
                dev.get(KEY_FAN_SPEED, FAN_LOW), "off"
            )
        else:
            self._attr_target_temperature = None
            self._attr_current_temperature = None
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_fan_mode = "off"

    @property
    def hvac_modes(self):
        if self._is_fresh_air:
            return [HVACMode.OFF, HVACMode.FAN_ONLY]
        return list(HVAC_MODES.values())

    @property
    def fan_modes(self):
        return list(FAN_MODES.values())

    # ---- Control methods ----

    async def async_set_temperature(self, **kwargs):
        target_temp = kwargs.get("temperature")
        if target_temp is not None:
            # Control API uses flat key "temp", not "iu31Temp"
            await self.coordinator.control(
                self._home_id, self._xkq_code, {CTRL_TEMP: int(target_temp)}
            )
            self._attr_target_temperature = target_temp
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.OFF:
            cmd = {CTRL_ONOFF: 0}
            self._attr_hvac_mode = HVACMode.OFF
        else:
            onoff = 1
            if self._is_fresh_air:
                mode_key = MODE_FAN_ONLY
            else:
                mode_key = {v: k for k, v in HVAC_MODES.items()}.get(hvac_mode, MODE_COOL)
            cmd = {CTRL_ONOFF: onoff, CTRL_MODE: mode_key}
            self._attr_hvac_mode = hvac_mode
        await self.coordinator.control(self._home_id, self._xkq_code, cmd)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str):
        fan_key = {v: k for k, v in FAN_MODES.items()}.get(fan_mode, FAN_LOW)
        # Control API uses flat key "wind", not "iu30Wind"
        await self.coordinator.control(
            self._home_id, self._xkq_code, {CTRL_WIND: fan_key}
        )
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()
