"""DataUpdateCoordinator for ha-hitachi-smart-home."""

from datetime import timedelta, datetime
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN, CONF_TOKEN, CONF_REFRESH_TOKEN, CODE_OK,
    KEY_STATE, KEY_TARGET_TEMP, KEY_MODE, KEY_FAN_SPEED, KEY_CUR_TEMP,
    KEY_TS, KEY_CODE, KEY_NAME, KEY_HOME_ID, KEY_DEVICE_TYPE, KEY_XKQ_TYPE,
    KEY_IU_NO, KEY_SYSTEM_NO, KEY_IU_SN, KEY_IU_TYPE, KEY_IEZ_CODE,
    KEY_VERSION_PROTOCOL, KEY_IS_XKQ,
    KEY_KEY_SOUND_SWITCH, KEY_INDOOR_HUMIDITY, KEY_INDOOR_PM25, KEY_REGION_CODE,
    MODE_COOL, MODE_HEAT, MODE_DRY, MODE_FAN_ONLY, MODE_AUTO,
    FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH,
    FAN_SPEED_AUTO, FAN_SPEED_BREEZE, FAN_SPEED_SUPER_LOW, FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM, FAN_SPEED_HIGH, FAN_SPEED_SUPER_HIGH,
)
from .api import HitachiApi

_LOGGER = logging.getLogger(__name__)

INTERVAL = timedelta(seconds=10)


class Coordinator(DataUpdateCoordinator[dict]):
    """Coordinator for Hitachi devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        token: str,
        refresh_token: str,
        config_entry=None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
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
        self._home_info: dict[str, dict] = {}  # home_id -> {"homeName": ..., "regionCode": ...}
        self._ts = datetime.now()

    async def _async_setup(self):
        """First-time setup: authenticate and discover devices."""
        _LOGGER.debug("Coordinator._async_setup")

        res = await self._auth()
        if not res:
            _LOGGER.debug("auth failed")
            raise ConfigEntryAuthFailed

        for home in res["data"]["homeList"]:
            home_id = str(home[KEY_HOME_ID])
            home_name = home.get("homeName", f"Home {home_id}")
            home_data = await self._api.get_home_detail(home_id, self._hass)
            if not home_data:
                _LOGGER.warning("Failed to get home detail for home_id %s", home_id)
                continue

            region_code = home_data.get("data", {}).get("homeDetail", {}).get(KEY_REGION_CODE, "")
            self._home_info[home_id] = {
                "homeName": home_name,
                KEY_REGION_CODE: region_code,
            }

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
                if not res or res.get("code") == "401":
                    _LOGGER.warning("Token expired (401), re-authenticating...")
                    if await self._auth():
                        res = await self._api.get_status(home_id, xkq_list, self._hass)
                if not res or res.get("code") != CODE_OK:
                    continue

                data = res.get("data", {})
                status_list = data.get("statusList", [])
                xkq_status_list = data.get("xkqStatusList", []) + data.get("xkqStatusListGjy", [])
                _LOGGER.debug(
                    "home %s: %d status groups, %d xkq statuses",
                    home_id, len(status_list), len(xkq_status_list)
                )

                # Build a lookup: iuId -> status values (standard indoor units)
                status_map = {}
                for group in status_list:
                    for value in group.get("values", []):
                        iu_id = value.get("iuId")
                        if iu_id:
                            status_map[iu_id] = value

                # Build a lookup: xkqCode -> status values (wire controllers)
                xkq_status_map = {}
                for item in xkq_status_list:
                    code = item.get("xkqCode")
                    if code:
                        xkq_status_map[code] = item

                # Update each device
                for xkq in xkq_list:
                    xkq_code = xkq[KEY_CODE]
                    if xkq.get(KEY_IS_XKQ):
                        matched = xkq_status_map.get(xkq_code)
                        if matched is None:
                            _LOGGER.warning("No status for XKQ device %s", xkq_code)
                            continue

                        # Running state (0=off, 1=on)
                        onoff = int(matched.get("if_run", matched.get("onoff", 0)))

                        # Target temperature (supports 0.5 step via set_temperature_add05)
                        target_temp = float(matched.get("set_temp", 26.0))
                        if str(matched.get("set_temperature_add05", "0")) == "1":
                            target_temp += 0.5

                        # Indoor ambient temperature
                        cur_temp = float(matched.get("indoor_temperature", 25.0))

                        # HVAC mode
                        if str(matched.get("wire_controller_makecold", "0")) == "1":
                            mode = MODE_COOL
                        elif str(matched.get("wire_controller_heating", "0")) == "1":
                            mode = MODE_HEAT
                        elif str(matched.get("wire_controller_rmwet", "0")) == "1":
                            mode = MODE_DRY
                        elif str(matched.get("wire_controller_makewind", "0")) == "1":
                            mode = MODE_FAN_ONLY
                        elif str(matched.get("wire_controller_auto", "0")) == "1":
                            mode = MODE_AUTO
                        else:
                            mode = xkq.get(KEY_MODE, MODE_COOL)

                        # 7-speed fan speed
                        if str(matched.get("wire_controller_wind_auto", "0")) == "1":
                            fan = FAN_SPEED_AUTO
                        elif str(matched.get("wire_controller_wind_superhigh", "0")) == "1":
                            fan = FAN_SPEED_SUPER_HIGH
                        elif str(matched.get("wire_controller_wind_high", "0")) == "1":
                            fan = FAN_SPEED_HIGH
                        elif str(matched.get("wire_controller_wind_mid", "0")) == "1":
                            fan = FAN_SPEED_MEDIUM
                        elif str(matched.get("wire_controller_wind_low", "0")) == "1":
                            fan = FAN_SPEED_LOW
                        elif str(matched.get("wire_controller_wind_superlow", "0")) == "1":
                            fan = FAN_SPEED_SUPER_LOW
                        elif str(matched.get("wire_controller_wind_light", "0")) == "1":
                            fan = FAN_SPEED_BREEZE
                        else:
                            fan = xkq.get(KEY_FAN_SPEED, FAN_SPEED_AUTO)

                        # Environmental & switches
                        indoor_hum = float(matched.get("indoor_humidity", 0))
                        indoor_pm25 = float(matched.get("indoor_pm25", 0))
                        key_sound = int(matched.get("key_sound_switch", 0))

                        xkq.update({
                            KEY_STATE: onoff,
                            KEY_TARGET_TEMP: target_temp,
                            KEY_MODE: mode,
                            KEY_FAN_SPEED: fan,
                            KEY_CUR_TEMP: cur_temp,
                            KEY_INDOOR_HUMIDITY: indoor_hum,
                            KEY_INDOOR_PM25: indoor_pm25,
                            KEY_KEY_SOUND_SWITCH: key_sound,
                            KEY_TS: int(time.time()),
                        })
                    else:
                        matched = status_map.get(xkq_code)
                        if matched is None:
                            _LOGGER.warning("No status for device %s", xkq_code)
                            continue

                        raw_wind = int(matched.get("iu30Wind", 2))
                        iu_fan_map = {
                            FAN_AUTO: FAN_SPEED_AUTO,
                            FAN_LOW: FAN_SPEED_LOW,
                            FAN_MEDIUM: FAN_SPEED_MEDIUM,
                            FAN_HIGH: FAN_SPEED_HIGH,
                        }
                        fan = iu_fan_map.get(raw_wind, FAN_SPEED_MEDIUM)

                        xkq.update({
                            KEY_STATE: int(matched.get("iu28Onoff", 0)),
                            KEY_TARGET_TEMP: float(matched.get("iu31Temp", 26.0)),
                            KEY_MODE: int(matched.get("iu29Mode", 1)),
                            KEY_FAN_SPEED: fan,
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
        if self.config_entry and self._token:
            new_data = {**self.config_entry.data, CONF_TOKEN: self._token}
            self._hass.config_entries.async_update_entry(self.config_entry, data=new_data)
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

    def get_home_info(self, home_id: str) -> dict:
        return self._home_info.get(home_id, {})



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
            KEY_IS_XKQ: dev.get(KEY_IS_XKQ, False),
            KEY_DEVICE_TYPE: dev.get(KEY_DEVICE_TYPE, "1"),
            KEY_XKQ_TYPE: dev.get(KEY_XKQ_TYPE, ""),
            KEY_IEZ_CODE: dev.get(KEY_IEZ_CODE, xkq_code[:12]),
            KEY_IU_NO: dev.get(KEY_IU_NO, ""),
            KEY_SYSTEM_NO: dev.get(KEY_SYSTEM_NO, ""),
            KEY_IU_SN: dev.get(KEY_IU_SN, dev.get("macImei", "")),
            KEY_IU_TYPE: dev.get(KEY_IU_TYPE, ""),
            KEY_VERSION_PROTOCOL: dev.get(KEY_VERSION_PROTOCOL, 11),
        }
        res = await self._api.control(device_info, cmd_dict, self._hass)
        if res and res.get("code") == "401":
            _LOGGER.warning("Control token expired (401), re-authenticating and retrying...")
            if await self._auth():
                res = await self._api.control(device_info, cmd_dict, self._hass)
        return res

