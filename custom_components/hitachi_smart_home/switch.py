"""Switch platform for ha-hitachi-smart-home."""

import logging

from homeassistant.components.switch import SwitchEntity
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
    KEY_IS_XKQ,
    KEY_XKQ_TYPE,
    KEY_KEY_SOUND_SWITCH,
    DEVICE_TYPE_NAMES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitachiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hitachi switches from a config entry."""
    coordinator = entry.runtime_data.coordinator
    devices = coordinator.get_devices()
    entities = []

    for home_id, home_devices in devices.items():
        for dev in home_devices["xkqList"]:
            # Only wire controllers support key sound switch
            if dev.get(KEY_IS_XKQ):
                entities.append(
                    HitachiKeySoundSwitch(home_id, dev[KEY_CODE], coordinator)
                )

    _LOGGER.debug("Adding %d switch entities", len(entities))
    async_add_entities(entities)


class HitachiKeySoundSwitch(CoordinatorEntity[Coordinator], SwitchEntity):
    """Switch entity for wire controller touch sound (key sound)."""

    _attr_has_entity_name = True
    _attr_translation_key = "key_sound_switch"

    def __init__(self, home_id: str, xkq_code: str, coordinator: Coordinator) -> None:
        """Initialize the key sound switch."""
        super().__init__(coordinator)
        self._home_id = home_id
        self._xkq_code = xkq_code
        self._attr_unique_id = f"hitachi-{self._home_id}-{self._xkq_code}-key_sound"

        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        name = dev.get(KEY_NAME, f"Hitachi {self._xkq_code}") if dev else f"Hitachi {self._xkq_code}"
        device_type = dev.get(KEY_XKQ_TYPE, "") if dev else ""
        model_name = DEVICE_TYPE_NAMES.get(device_type, "智能线控器")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"hitachi_{self._home_id}_{self._xkq_code}")},
            name=name,
            manufacturer="Hisense Hitachi",
            model=model_name,
        )
        self._update_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        """Update switch state from coordinator device data."""
        dev = self.coordinator.get_data(self._home_id, self._xkq_code)
        if dev:
            self._attr_is_on = bool(dev.get(KEY_KEY_SOUND_SWITCH, 0) == 1)
        else:
            self._attr_is_on = False

    @property
    def icon(self) -> str:
        """Return the icon based on switch state."""
        return "mdi:volume-high" if self._attr_is_on else "mdi:volume-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the key sound switch on."""
        await self.coordinator.control(
            self._home_id, self._xkq_code, {KEY_KEY_SOUND_SWITCH: 1}
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the key sound switch off."""
        await self.coordinator.control(
            self._home_id, self._xkq_code, {KEY_KEY_SOUND_SWITCH: 0}
        )
        self._attr_is_on = False
        self.async_write_ha_state()
