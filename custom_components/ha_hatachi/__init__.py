"""ha-hatachi integration for Hisense Hitachi Central AC."""

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_TOKEN, CONF_REFRESH_TOKEN
from .coordinator import Coordinator

PLATFORMS = [Platform.CLIMATE]

_LOGGER = logging.getLogger(__name__)


@dataclass
class HitachiData:
    coordinator: Coordinator


type HitachiConfigEntry = ConfigEntry[HitachiData]


async def async_setup_entry(hass: HomeAssistant, entry: HitachiConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    token = entry.data[CONF_TOKEN]
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN, "")

    coordinator = Coordinator(hass, username, password, token, refresh_token)
    entry.runtime_data = HitachiData(coordinator=coordinator)

    # First refresh triggers _async_setup -> auth + device discovery
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("async_setup_entry finished")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HitachiConfigEntry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
