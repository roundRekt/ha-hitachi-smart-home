"""API client for Hitachi Smart Home."""

import time
import logging
import asyncio
from collections import defaultdict

from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    API_DOMAIN, API_LOGIN, API_HOMES, API_STATUS, API_CONTROL,
    HEADER_APIKEY, HEADER_APPID, HEADER_OS, HEADER_VERSION,
    HEADER_APPTAG, HEADER_LOCALE, HEADER_HOST, HEADER_USER_AGENT,
    JG_REG_ID, LOGIN_VERSION, CODE_OK,
    KEY_CODE, KEY_NAME, KEY_HOME_ID, KEY_DEVICE_TYPE, KEY_XKQ_TYPE, KEY_MAC,
    KEY_IU_NO, KEY_SYSTEM_NO, KEY_IU_SN, KEY_IU_TYPE, KEY_IEZ_CODE,
    KEY_VERSION_PROTOCOL, KEY_IS_XKQ, KEY_HALF_SUPPORT,
    KEY_STATE, KEY_TARGET_TEMP, KEY_MODE, KEY_FAN_SPEED, KEY_CUR_TEMP, KEY_TS,
    FAN_MEDIUM, MODE_COOL,
)

_LOGGER = logging.getLogger(__name__)


class HitachiApi:
    """HTTP client for Hitachi cloud API."""

    def __init__(self, username: str, password: str, token: str = ""):
        self._username = username
        self._password = password
        self._token = token

    def _headers(self) -> dict:
        h = {
            "Host": HEADER_HOST,
            "accept-charset": "UTF-8",
            "x-his-locale": HEADER_LOCALE,
            "x-his-apikey": HEADER_APIKEY,
            "x-his-timestamp": str(int(time.time() * 1000)),
            "x-his-appid": HEADER_APPID,
            "x-his-os": HEADER_OS,
            "x-his-version": HEADER_VERSION,
            "x-his-apptag": HEADER_APPTAG,
            "content-type": "application/json",
            "user-agent": HEADER_USER_AGENT,
            "accept-encoding": "gzip",
        }
        if self._token:
            h["authorization"] = f"Bearer {self._token}"
        return h

    # ---- Auth ----

    async def login(self, hass) -> dict | None:
        """POST /login with JSON body (exact match to working plugin)."""
        url = f"{API_DOMAIN}/{API_LOGIN}"
        body = {
            "phoneNo": self._username,
            "password": self._password,
            "jgRegId": JG_REG_ID,
            "version": LOGIN_VERSION,
        }
        _LOGGER.debug("login: %s", url)
        async with get_async_client(hass) as client:
            resp = await client.post(url, json=body, headers=self._headers())
            data = resp.json()
        _LOGGER.debug("login response code=%s", data.get("code"))
        if data.get("code") == CODE_OK:
            user = data["data"]["user"]
            self._token = user["token"]
            return data
        _LOGGER.error("login failed: %s", data)
        return None

    async def refresh_auth(self, hass) -> dict | None:
        """Re-login to refresh token."""
        return await self.login(hass)

    # ---- Home & Device Discovery ----

    async def get_home_detail(self, home_id: str, hass) -> dict | None:
        """GET /api/apphome/homes/{home_id}"""
        url = f"{API_DOMAIN}/{API_HOMES}/{home_id}"
        _LOGGER.debug("get_home_detail: %s", url)
        async with get_async_client(hass) as client:
            resp = await client.get(url, headers=self._headers())
            data = resp.json()
        if data.get("code") == CODE_OK:
            return data
        _LOGGER.error("get_home_detail failed: %s", data)
        return None

    def extract_devices(self, home_data: dict, home_id: str) -> list[dict]:
        """Extract indoor units and wire controllers from home detail response."""
        devices = []
        existing_codes = set()
        home_detail = home_data.get("data", {}).get("homeDetail", {})

        # 1. Gateway indoor units (iuList under deviceList)
        for device in home_detail.get("deviceList", []):
            device_type = device.get("type", "")
            iez_code = device.get("iezCode", "")
            version_proto = device.get("versionModbusProtocol", 11)
            for iu in device.get("iuList", []):
                code = iu["iuId"]
                if code in existing_codes:
                    continue
                existing_codes.add(code)
                dev = {
                    KEY_CODE: code,
                    KEY_NAME: iu.get("iuName", ""),
                    KEY_XKQ_TYPE: iu.get("iuType", ""),
                    KEY_DEVICE_TYPE: device_type,
                    KEY_HOME_ID: home_id,
                    KEY_IS_XKQ: False,
                    # Device identity for control commands
                    KEY_IEZ_CODE: iez_code,
                    KEY_IU_NO: iu.get("iuNo", ""),
                    KEY_SYSTEM_NO: iu.get("systemNo", ""),
                    KEY_IU_SN: iu.get("iuSn", ""),
                    KEY_IU_TYPE: iu.get("iuType", ""),
                    KEY_VERSION_PROTOCOL: version_proto,
                    # Capability limits
                    "heatMax": iu.get("heatMax", 32),
                    "heatMin": iu.get("heatMin", 16),
                    "coldMax": iu.get("coldMax", 32),
                    "coldMin": iu.get("coldMin", 16),
                    KEY_HALF_SUPPORT: iu.get("halfSupport", 0),
                    KEY_MAC: iu.get("iuSn", ""),
                    KEY_TS: 0,
                    # Default state fields (will be filled by status poll)
                    KEY_STATE: 0,
                    KEY_TARGET_TEMP: 26.0,
                    KEY_MODE: MODE_COOL,
                    KEY_FAN_SPEED: FAN_MEDIUM,
                    KEY_CUR_TEMP: 25.0,
                }
                devices.append(dev)
                _LOGGER.debug("found indoor unit: %s (%s)", code, iu.get("iuName", ""))

        # 2. Wire controllers (xkqList)
        for xkq in home_detail.get("xkqList", []):
            xkq_code = xkq.get("xkqCode")
            if not xkq_code or xkq_code in existing_codes:
                continue
            existing_codes.add(xkq_code)
            dev = {
                KEY_CODE: xkq_code,
                KEY_NAME: xkq.get("xkqName", f"线控器 {xkq_code[-4:]}"),
                KEY_XKQ_TYPE: xkq.get("xkqType", "13"),
                KEY_DEVICE_TYPE: xkq.get("type", "C"),
                KEY_HOME_ID: home_id,
                KEY_IS_XKQ: True,
                # Device identity for control commands
                KEY_IEZ_CODE: xkq_code,
                KEY_MAC: xkq.get("macImei", ""),
                KEY_VERSION_PROTOCOL: xkq.get("versionModbusProtocol", 29952),
                # Capability limits
                "heatMax": xkq.get("heatMax", 32),
                "heatMin": xkq.get("heatMin", 8),
                "coldMax": xkq.get("coldMax", 32),
                "coldMin": xkq.get("coldMin", 16),
                KEY_HALF_SUPPORT: xkq.get("halfSupport", 0),
                KEY_TS: 0,
                # Default state fields (will be filled by status poll)
                KEY_STATE: 0,
                KEY_TARGET_TEMP: 26.0,
                KEY_MODE: MODE_COOL,
                KEY_FAN_SPEED: FAN_MEDIUM,
                KEY_CUR_TEMP: 25.0,
            }
            devices.append(dev)
            _LOGGER.debug("found wire controller: %s (%s)", xkq_code, dev[KEY_NAME])

        return devices

    # ---- Status ----

    async def get_status(self, home_id: str, devices: list[dict], hass) -> dict | None:
        """POST /api/appstatus/homes/{home_id}/status"""
        iu_devices = [d for d in devices if not d.get(KEY_IS_XKQ)]
        xkq_devices = [d for d in devices if d.get(KEY_IS_XKQ)]

        # Build iuIdList from IU devices, grouping by iezCode (first 12 chars)
        iez_groups: dict[str, list] = defaultdict(list)
        for dev in iu_devices:
            full_code = dev[KEY_CODE]
            iez_code = full_code[:12]
            iez_groups[iez_code].append({
                "iuId": full_code,
                "timestamp": dev.get(KEY_TS, 0)
            })

        iu_id_list = [
            {"iezCode": iez, "iuIds": iu_ids}
            for iez, iu_ids in iez_groups.items()
        ]

        # Build xkqList from XKQ devices
        xkq_id_list = [
            {"xkqCode": dev[KEY_CODE], "timestamp": dev.get(KEY_TS, 0)}
            for dev in xkq_devices
        ]

        body = {
            "homeId": int(home_id),
            "noNetTip": True,
            "iuIdListGjy": [],
            "boxList": [],
            "xkqList": xkq_id_list,
            "xkqListGjy": xkq_id_list,
            "iuIdList": iu_id_list,
        }

        url = f"{API_DOMAIN}/{API_STATUS}/{home_id}/status"
        _LOGGER.debug("get_status: %s (iu=%d, xkq=%d)", url, len(iu_devices), len(xkq_devices))
        async with get_async_client(hass) as client:
            resp = await client.post(url, json=body, headers=self._headers())
            data = resp.json()
        if data.get("code") == CODE_OK:
            return data
        _LOGGER.error("get_status failed: %s", data)
        return None

    # ---- Control ----

    async def control(self, device_info: dict, cmd_dict: dict, hass) -> dict | None:
        """POST /api/appcontrol/cmds/multiIuOuCtrl"""
        is_xkq = device_info.get(KEY_IS_XKQ, False)

        if is_xkq:
            ctrl_list = []
            xkq_ctrl_list = [
                {
                    "xkqCode": device_info[KEY_CODE],
                    "xkqType": device_info.get(KEY_XKQ_TYPE, "13"),
                    "deviceType": device_info.get(KEY_DEVICE_TYPE, "C"),
                    "ctrlJson": cmd_dict,
                }
            ]
        else:
            ctrl_list = [
                {
                    "iuCtrlInfo": [
                        {
                            "ctrlJson": cmd_dict,
                            "iuNo": device_info[KEY_IU_NO],
                            "iuSn": device_info[KEY_IU_SN],
                            "iuType": device_info[KEY_IU_TYPE],
                            "systemNo": device_info[KEY_SYSTEM_NO],
                        }
                    ],
                    "ouCtrlInfo": [],
                    "deviceType": device_info[KEY_DEVICE_TYPE],
                    "iezCode": device_info[KEY_IEZ_CODE],
                    "versionModbusProtocol": device_info.get(KEY_VERSION_PROTOCOL, 11),
                }
            ]
            xkq_ctrl_list = []

        body = {
            "ctrlList": ctrl_list,
            "xkqCtrlList": xkq_ctrl_list,
            "homeId": int(device_info[KEY_HOME_ID]),
            "ctrlType": "HA420",
            "regionCode": "0",
            "positionLat": 4.9e-324,
            "positionLng": 4.9e-324,
            "position1": "  ",
            "position2": "",
            "positionCity": "",
        }

        url = f"{API_DOMAIN}/{API_CONTROL}"
        _LOGGER.debug("control: %s is_xkq=%s ctrlJson=%s", url, is_xkq, cmd_dict)
        async with get_async_client(hass) as client:
            resp = await client.post(url, json=body, headers=self._headers())
            data = resp.json()
        _LOGGER.debug("control response code=%s", data.get("code"))
        # Wait a moment for the command to take effect
        await asyncio.sleep(3)
        return data



    # ---- Token management ----

    @property
    def token(self) -> str:
        return self._token

    def set_token(self, token: str):
        self._token = token
