"""Config flow for ha-hatachi."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_TOKEN, CONF_REFRESH_TOKEN
from .api import HitachiApi

_LOGGER = logging.getLogger(__name__)


class HatachiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ha-hatachi."""

    VERSION = 1

    def __init__(self):
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        if user_input is not None:
            self._user_input.update(user_input)
            _LOGGER.debug("Authenticating...")
            api = HitachiApi(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            res = await api.login(self.hass)
            if res is not None:
                user_data = res["data"]["user"]
                self._user_input[CONF_TOKEN] = user_data["token"]
                self._user_input[CONF_REFRESH_TOKEN] = user_data.get("refreshToken", "")
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=self._user_input
                )
            else:
                errors = {"base": "invalid_login"}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )
