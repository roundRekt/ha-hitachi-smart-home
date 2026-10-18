"""Sensor platform for ha-hitachi-smart-home."""

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
)

try:
    from homeassistant.const import UnitOfDensity
    PM25_UNIT = UnitOfDensity.MICROGRAMS_PER_CUBIC_METER
except ImportError:
    from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    PM25_UNIT = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HitachiConfigEntry
from .coordinator import Coordinator
from .const import (
    DOMAIN,
    KEY_CODE,
    KEY_NAME,
    KEY_CUR_TEMP,
    KEY_IS_XKQ,
    KEY_XKQ_TYPE,
    KEY_INDOOR_HUMIDITY,
    KEY_INDOOR_PM25,
    DEVICE_TYPE_NAMES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitachiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hitachi sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    devices = coordinator.get_devices()
    entities: list[SensorEntity] = []

    for home_id, home_devices in devices.items():
        # Device sensors (Indoor temperature, humidity, PM2.5)
        for dev in home_devices["xkqList"]:
            code = dev[KEY_CODE]
            # Indoor temperature sensor for every unit
            entities.append(
                HitachiIndoorTemperatureSensor(home_id, code, coordinator)
            )

            # Humidity & PM2.5 sensors for wire controllers
            if dev.get(KEY_IS_XKQ):
                entities.append(
                    HitachiIndoorHumiditySensor(home_id, code, coordinator)
                )
                entities.append(
                    HitachiIndoorPM25Sensor(home_id, code, coordinator)
                )

    _LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Device Indoor Sensors
# ---------------------------------------------------------------------------

class HitachiIndoorBaseSensor(CoordinatorEntity[Coordinator], SensorEntity):
    """Base class for indoor device sensors."""

    _attr_has_entity_name = True

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator) -> None:
        """Initialize the base indoor sensor."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._xkq_code = xkq_code

        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        name = dev.get(KEY_NAME, f"Hitachi {self._xkq_code}") if dev else f"Hitachi {self._xkq_code}"
        device_type = dev.get(KEY_XKQ_TYPE, "") if dev else ""
        is_xkq = dev.get(KEY_IS_XKQ, False) if dev else False
        model_name = DEVICE_TYPE_NAMES.get(device_type, "智能线控器" if is_xkq else "中央空调室内机")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"hitachi_{self._home_id}_{self._xkq_code}")},
            name=name,
            manufacturer="Hisense Hitachi",
            model=model_name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        """Update sensor state. Implemented in subclasses."""
        pass


class HitachiIndoorTemperatureSensor(HitachiIndoorBaseSensor):
    """Indoor temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "indoor_temperature"

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator) -> None:
        super().__init__(home_id, xkq_code, coordinator)
        self._attr_unique_id = f"hitachi-{self._home_id}-{self._xkq_code}-temperature"
        self._update_state()

    def _update_state(self) -> None:
        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        if dev:
            self._attr_native_value = dev.get(KEY_CUR_TEMP)
        else:
            self._attr_native_value = None


class HitachiIndoorHumiditySensor(HitachiIndoorBaseSensor):
    """Indoor humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "indoor_humidity"

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator) -> None:
        super().__init__(home_id, xkq_code, coordinator)
        self._attr_unique_id = f"hitachi-{self._home_id}-{self._xkq_code}-indoor_humidity"
        self._update_state()

    def _update_state(self) -> None:
        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        if dev:
            hum = dev.get(KEY_INDOOR_HUMIDITY, 0)
            self._attr_native_value = hum if hum > 0 else None
        else:
            self._attr_native_value = None


class HitachiIndoorPM25Sensor(HitachiIndoorBaseSensor):
    """Indoor PM2.5 sensor."""

    _attr_device_class = SensorDeviceClass.PM25
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PM25_UNIT
    _attr_translation_key = "indoor_pm25"

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator) -> None:
        super().__init__(home_id, xkq_code, coordinator)
        self._attr_unique_id = f"hitachi-{self._home_id}-{self._xkq_code}-indoor_pm25"
        self._update_state()

    def _update_state(self) -> None:
        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        if dev:
            pm = dev.get(KEY_INDOOR_PM25, 0)
            self._attr_native_value = pm if pm > 0 else None
        else:
            self._attr_native_value = None



