"""Constants for ha-hitachi-smart-home integration."""

DOMAIN = "hitachi_smart_home"
CONF_TOKEN = "token"
CONF_REFRESH_TOKEN = "refresh_token"

# API
API_DOMAIN = "https://1app.hicloud.hisensehitachi.com"
API_LOGIN = "login"
API_RT_LOGIN = "rtLogin"
API_HOMES = "api/apphome/homes"
API_STATUS = "api/appstatus/homes"
API_CONTROL = "api/appcontrol/cmds/multiIuOuCtrl"

# Request headers (from working plugin)
HEADER_APIKEY = "1QiLCJhbGciOiJIUzI1NiJ9"
HEADER_APPID = "com.hisensehitachi.iez2"
HEADER_OS = "Android"
HEADER_VERSION = "7.5.3.260417183002_release"
HEADER_APPTAG = "V3"
HEADER_LOCALE = "zh_CN"
HEADER_HOST = "1app.hicloud.hisensehitachi.com"
HEADER_USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 12; V2304A Build/W528JS)"

# Login params (from working plugin)
JG_REG_ID = "1507bfd3f6ce767df06"
LOGIN_VERSION = 0

# Response codes
CODE_OK = "200"

# Device keys (internal storage)
KEY_CODE = "xkqCode"
KEY_NAME = "xkqName"
KEY_HOME_ID = "homeId"
KEY_IS_XKQ = "isXkq"
# ---- Status fields (read from API) ----
KEY_STATE = "iu28Onoff"
KEY_TARGET_TEMP = "iu31Temp"
KEY_MODE = "iu29Mode"
KEY_FAN_SPEED = "iu30Wind"
KEY_CUR_TEMP = "iu39Ti"
KEY_TS = "timestamp"
# ---- Device metadata ----
KEY_DEVICE_TYPE = "deviceType"
KEY_XKQ_TYPE = "xkqType"
KEY_HEAT_MAX = "heatMax"
KEY_HEAT_MIN = "heatMin"
KEY_COLD_MAX = "coldMax"
KEY_COLD_MIN = "coldMin"
KEY_HALF_SUPPORT = "halfSupport"
KEY_MAC = "macImei"
# ---- Control payload fields (needed per device) ----
KEY_IU_NO = "iuNo"
KEY_SYSTEM_NO = "systemNo"
KEY_IU_SN = "iuSn"
KEY_IU_TYPE = "iuType"
KEY_IEZ_CODE = "iezCode"
KEY_VERSION_PROTOCOL = "versionModbusProtocol"
# ---- Control command keys (flat names, not iuXX prefixed) ----
CTRL_ONOFF = "onoff"
CTRL_TEMP = "temp"
CTRL_MODE = "mode"
CTRL_WIND = "wind"

# Device types
DEVICE_TYPE_CLIMATE = "05"
DEVICE_TYPE_SPECIAL = "03"
DEVICE_TYPE_FRESH_AIR = "0D"
DEVICE_TYPE_WIRE_CONTROLLER = "13"

DEVICE_TYPE_NAMES = {
    DEVICE_TYPE_CLIMATE: "标准空调",
    DEVICE_TYPE_SPECIAL: "特殊机型",
    DEVICE_TYPE_FRESH_AIR: "新风系统",
    DEVICE_TYPE_WIRE_CONTROLLER: "智能线控器",
    "C": "线控器",
}

# HVAC mode mapping (from working plugin climate.py)
# mode values in API: 0=off, 1=cool, 2=dry, 3=fan_only, 4=heat, 5=auto
MODE_OFF = 0
MODE_COOL = 1
MODE_DRY = 2
MODE_FAN_ONLY = 3
MODE_HEAT = 4
MODE_AUTO = 5

# Fan speed mapping (Gateway IU numeric API status: 0=auto, 1=low, 2=medium, 3=high)
FAN_AUTO = 0
FAN_LOW = 1
FAN_MEDIUM = 2
FAN_HIGH = 3

# Fan mode strings (used in Home Assistant climate entity)
FAN_SPEED_AUTO = "auto"
FAN_SPEED_BREEZE = "breeze"
FAN_SPEED_SUPER_LOW = "super_low"
FAN_SPEED_LOW = "low"
FAN_SPEED_MEDIUM = "medium"
FAN_SPEED_HIGH = "high"
FAN_SPEED_SUPER_HIGH = "super_high"

# Standard Gateway IU fan modes
IU_FAN_MODES = [
    FAN_SPEED_AUTO,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    FAN_SPEED_HIGH,
]

# XKQ 7-speed fan modes
XKQ_FAN_MODES = [
    FAN_SPEED_AUTO,
    FAN_SPEED_BREEZE,
    FAN_SPEED_SUPER_LOW,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    FAN_SPEED_HIGH,
    FAN_SPEED_SUPER_HIGH,
]

# Map XKQ fan mode to control command payload
XKQ_FAN_CMD_MAP = {
    FAN_SPEED_AUTO: "wire_controller_wind_auto",
    FAN_SPEED_BREEZE: "wire_controller_wind_light",
    FAN_SPEED_SUPER_LOW: "wire_controller_wind_superlow",
    FAN_SPEED_LOW: "wire_controller_wind_low",
    FAN_SPEED_MEDIUM: "wire_controller_wind_mid",
    FAN_SPEED_HIGH: "wire_controller_wind_high",
    FAN_SPEED_SUPER_HIGH: "wire_controller_wind_superhigh",
}

# Additional entity keys
KEY_KEY_SOUND_SWITCH = "key_sound_switch"
KEY_INDOOR_HUMIDITY = "indoor_humidity"
KEY_INDOOR_PM25 = "indoor_pm25"
KEY_REGION_CODE = "regionCode"

# Wire controller (XKQ) control command constants
XKQ_CTRL_RUN = "if_run"
XKQ_CTRL_TEMP = "set_temp"
XKQ_CTRL_ADD05 = "set_temperature_add05"

XKQ_MODE_CMD_COOL = "wire_controller_makecold"
XKQ_MODE_CMD_HEAT = "wire_controller_heating"
XKQ_MODE_CMD_DRY = "wire_controller_rmwet"
XKQ_MODE_CMD_FAN_ONLY = "wire_controller_makewind"
XKQ_MODE_CMD_AUTO = "wire_controller_auto"

XKQ_MODE_CMD_MAP = {
    MODE_COOL: XKQ_MODE_CMD_COOL,
    MODE_HEAT: XKQ_MODE_CMD_HEAT,
    MODE_DRY: XKQ_MODE_CMD_DRY,
    MODE_FAN_ONLY: XKQ_MODE_CMD_FAN_ONLY,
    MODE_AUTO: XKQ_MODE_CMD_AUTO,
}

