"""DataUpdateCoordinator for ha-hatachi."""

from datetime import timedelta, datetime
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN, CONF_REFRESH_TOKEN, CODE_OK,
    KEY_STATE, KEY_TARGET_TEMP, KEY_MODE, KEY_FAN_SPEED, KEY_CUR_TEMP,
    KEY_TS, KEY_CODE, KEY_NAME, KEY_HOME_ID, KEY_DEVICE_TYPE, KEY_XKQ_TYPE,
    KEY_IU_NO, KEY_SYSTEM_NO, KEY_IU_SN, KEY_IU_TYPE, KEY_IEZ_CODE,
    KEY_VERSION_PROTOCOL,
)
from .api import HitachiApi

_LOGGER = logging.getLogger(__name__)

INTERVAL = timedelta(seconds=10)


class Coordinator(DataUpdateCoordinator[dict]):
    """Coordinator for Hisense Hitachi devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        token: str,
        refresh_token: str,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Hitachi",
            update_interval=INTERVAL,
            always_update=True,
        )
        self._hass = hass
        self._username = username
        self._password = password
        self._token = token
        self._refresh_token = refresh_token
        self._api = HitachiApi(username, password, token)
        self._devices: dict[str, dict] = {}  # home_id -> {"xkqList": [...]}
        self._ts = datetime.now()

    async def _async_setup(self):
        """First-time setup: authenticate and discover devices."""
        _LOGGER.debug("Coordinator._async_setup")

        res = await self._auth()
        if not res:
            _LOGGER.debug("auth failed")
            raise ConfigEntryAuthFailed

        for home in res["data"]["homeList"]:
            home_id = home[KEY_HOME_ID]
            home_data = await self._api.get_home_detail(home_id, self._hass)
            if not home_data:
                _LOGGER.warning("Failed to get home detail for home_id %s", home_id)
                continue

            devices = self._api.extract_devices(home_data, home_id)
            if not devices:
                _LOGGER.warning("No devices found for home_id %s", home_id)
                continue

            self._devices[home_id] = {"xkqList": devices}
            _LOGGER.debug("home_id %s: %d devices", home_id, len(devices))

        _LOGGER.debug("Devices discovered: %s", self._devices)

    async def _async_update_data(self) -> dict:
        """Poll device status every INTERVAL seconds."""
        _LOGGER.debug("Coordinator._async_update_data")

        # Refresh auth every 24 hours
        await self._refresh_auth()

        try:
            for home_id, home_devices in self._devices.items():
                xkq_list = home_devices["xkqList"]
                res = await self._api.get_status(home_id, xkq_list, self._hass)
                if not res:
                    continue

                status_list = res.get("data", {}).get("statusList", [])
                _LOGGER.debug("home %s: %d status groups", home_id, len(status_list))

                # Build a lookup: iuId -> status values
                status_map = {}
                for group in status_list:
                    for value in group.get("values", []):
                        iu_id = value.get("iuId")
                        if iu_id:
                            status_map[iu_id] = value

                # Update each device
                for xkq in xkq_list:
                    xkq_code = xkq[KEY_CODE]
                    matched = status_map.get(xkq_code)
                    if matched is None:
                        _LOGGER.warning("No status for device %s", xkq_code)
                        continue

                    xkq.update({
                        KEY_STATE: int(matched.get("iu28Onoff", 0)),
                        KEY_TARGET_TEMP: float(matched.get("iu31Temp", 26.0)),
                        KEY_MODE: int(matched.get("iu29Mode", 1)),
                        KEY_FAN_SPEED: int(matched.get("iu30Wind", 2)),
                        KEY_CUR_TEMP: float(matched.get("iu39Ti", 25.0)),
                        KEY_TS: int(time.time()),
                    })

                _LOGGER.debug("Updated %d devices for home %s",
                              len(xkq_list), home_id)

            return self._devices
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    async def _auth(self):
        """Authenticate and store new token."""
        par = await self._api.login(self._hass)
        if not par:
            return False

        self._token = self._api.token
        _LOGGER.debug("auth success")
        return par

    async def _refresh_auth(self):
        """Re-login once per day."""
        now = datetime.now()
        if now - self._ts > timedelta(days=1):
            self._ts = now
            try:
                _LOGGER.debug("refresh auth")
                await self._auth()
            except Exception:
                _LOGGER.error("auth poll failed", exc_info=True)

    # ---- Public helpers ----

    def get_devices(self) -> dict:
        return self._devices

    def get_data(self, home_id: str, xkq_code: str) -> dict | None:
        devices = self._devices.get(home_id, {}).get("xkqList", [])
        for dev in devices:
            if dev[KEY_CODE] == xkq_code:
                return dev
        return None

    async def control(self, home_id: str, xkq_code: str, cmd_dict: dict):
        dev = self.get_data(home_id, xkq_code)
        if not dev:
            _LOGGER.error("Device not found: %s/%s", home_id, xkq_code)
            return None
        device_info = {
            KEY_HOME_ID: home_id,
            KEY_CODE: xkq_code,
            KEY_DEVICE_TYPE: dev.get(KEY_DEVICE_TYPE, "1"),
            KEY_XKQ_TYPE: dev.get(KEY_XKQ_TYPE, ""),
            KEY_IEZ_CODE: dev.get(KEY_IEZ_CODE, xkq_code[:12]),
            KEY_IU_NO: dev.get(KEY_IU_NO, ""),
            KEY_SYSTEM_NO: dev.get(KEY_SYSTEM_NO, ""),
            KEY_IU_SN: dev.get(KEY_IU_SN, dev.get("macImei", "")),
            KEY_IU_TYPE: dev.get(KEY_IU_TYPE, ""),
            KEY_VERSION_PROTOCOL: dev.get(KEY_VERSION_PROTOCOL, 11),
        }
        return await self._api.control(device_info, cmd_dict, self._hass)
