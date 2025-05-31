"""
Daikin Alira climate platform with On/Off, temperature, fan-speed, and mode control.

Supported features:
  - On/Off
  - Target temperature (16–30 °C, 0.5 °C step)
  - Fan modes (1, 2, 3, 4, 5, Auto, Quiet)
  - Operation modes (Auto, Cool, Heat, Fan only, Dry)
"""

import logging
import aiohttp

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)

from .const import DOMAIN
from .sensor import fetch_status

_LOGGER = logging.getLogger(__name__)

# HVAC mode strings Home Assistant expects
HVAC_MODE_OFF = "off"
HVAC_MODE_AUTO = "auto"
HVAC_MODE_COOL = "cool"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_FAN_ONLY = "fan_only"
HVAC_MODE_DRY = "dry"

SUPPORTED_HVAC_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
]

# Supported features: target temperature and fan mode (hvac_modes are implicit)
_ATTR_SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
)

# Temperature range (°C)
MIN_TEMP = 16.0
MAX_TEMP = 30.0
TEMP_STEP = 0.5

# Hard-coded Celsius unit
_TEMP_UNIT = "°C"

# Fan-speed mappings (hex ↔ human)
FAN_SPEED_MAP = {
    "0300": "1",
    "0400": "2",
    "0500": "3",
    "0600": "4",
    "0700": "5",
    "0A00": "Auto",
    "0B00": "Quiet",
}
FAN_SPEED_REVERSE_MAP = {v: k for k, v in FAN_SPEED_MAP.items()}

# Operation-mode mappings (hex ↔ Home Assistant string)
MODE_MAP = {
    "0300": HVAC_MODE_AUTO,
    "0200": HVAC_MODE_COOL,
    "0100": HVAC_MODE_HEAT,
    "0000": HVAC_MODE_FAN_ONLY,
    "0500": HVAC_MODE_DRY,
}
MODE_REVERSE_MAP = {v: k for k, v in MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Daikin Alira climate entity with full control."""
    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}-{host}-climate",
        update_method=lambda: fetch_status(session, host),
        update_interval=None,
    )

    try:
        # Perform an initial data fetch
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.error("Climate: initial fetch failed: %s", e)
        return

    async_add_entities([DaikinClimate(coordinator, host)], True)


class DaikinClimate(CoordinatorEntity, ClimateEntity):
    """Daikin Alira climate entity with On/Off, temperature, fan, and HVAC mode control."""

    _attr_name = "Daikin AC"
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_supported_features = _ATTR_SUPPORTED_FEATURES
    _attr_temperature_unit = _TEMP_UNIT

    @property
    def min_temp(self) -> float:
        return MIN_TEMP

    @property
    def max_temp(self) -> float:
        return MAX_TEMP

    @property
    def target_temperature_step(self) -> float:
        return TEMP_STEP

    @property
    def fan_modes(self) -> list[str]:
        return list(FAN_SPEED_REVERSE_MAP.keys())

    @property
    def hvac_modes(self) -> list[str]:
        return SUPPORTED_HVAC_MODES

    def __init__(self, coordinator: DataUpdateCoordinator, host: str):
        super().__init__(coordinator)
        self.host = host
        self._attr_unique_id = f"{DOMAIN}_{host}_climate"

    @property
    def device_info(self) -> dict:
        """
        Return device info so that climate and sensors share one device.

        Uses the same identifier that sensor.py used: (DOMAIN, "daikin_alira-<host>").
        """
        return {
            "identifiers": {(DOMAIN, f"{DOMAIN}-{self.host}" )},
            "name": "Daikin Alira",
            "manufacturer": "Daikin",
            "model": "Alira",
        }

    @property
    def hvac_mode(self) -> str:
        """
        Return the current HVAC mode:
          - If power PV != "01", return OFF
          - Otherwise, read the mode hex under e_1002 → e_3001 → p_00 and map via MODE_MAP
        """
        try:
            power_hex = self._get_power_value()
            if power_hex != "01":
                return HVAC_MODE_OFF

            node = self.coordinator.data
            level1 = next(item for item in node if item.get("pn") == "e_1002")
            level2 = next(
                item for item in level1.get("pch", []) if item.get("pn") == "e_3001"
            )
            mode_hex = level2.get("pch", [])[0].get("pv", "")
            return MODE_MAP.get(mode_hex, HVAC_MODE_OFF)
        except Exception as e:
            _LOGGER.warning("Climate: failed to read hvac_mode: %s", e)
            return HVAC_MODE_OFF

    @property
    def current_temperature(self) -> float | None:
        """
        Return the current indoor temperature (°C),
        drilled from e_1002 → e_A00B → [0] → pv (little-endian hex).
        """
        try:
            node = self.coordinator.data
            level1 = next(item for item in node if item.get("pn") == "e_1002")
            level2 = next(
                item for item in level1.get("pch", []) if item.get("pn") == "e_A00B"
            )
            hexstr = level2.get("pch", [])[0].get("pv", "")
            return int.from_bytes(bytes.fromhex(hexstr), "little")
        except Exception as e:
            _LOGGER.debug("Climate: failed to read current_temperature: %s", e)
            return None

    @property
    def target_temperature(self) -> float | None:
        """
        Return the current setpoint temperature (°C),
        drilled from e_1002 → e_3001 → [2] → pv (little-endian hex ÷ 2).
        """
        try:
            node = self.coordinator.data
            level1 = next(item for item in node if item.get("pn") == "e_1002")
            level2 = next(
                item for item in level1.get("pch", []) if item.get("pn") == "e_3001"
            )
            hexstr = level2.get("pch", [])[2].get("pv", "")
            raw = int.from_bytes(bytes.fromhex(hexstr), "little")
            return raw / 2.0
        except Exception as e:
            _LOGGER.debug("Climate: failed to read target_temperature: %s", e)
            return None

    @property
    def fan_mode(self) -> str | None:
        """
        Return the current fan mode ("1","2","3","4","5","Auto","Quiet"),
        drilled from e_1002 → e_3001 → [8] → pv and mapped via FAN_SPEED_MAP.
        """
        try:
            node = self.coordinator.data
            level1 = next(item for item in node if item.get("pn") == "e_1002")
            level2 = next(
                item for item in level1.get("pch", []) if item.get("pn") == "e_3001"
            )
            hexstr = level2.get("pch", [])[8].get("pv", "")
            return FAN_SPEED_MAP.get(hexstr, None)
        except Exception as e:
            _LOGGER.debug("Climate: failed to read fan_mode: %s", e)
            return None

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """
        Change the HVAC mode. Two cases:
          - If hvac_mode == "off": set power=00 only.
          - Otherwise: set power=01, then set mode via p_00 to correct hex.
        """
        # Turn OFF
        if hvac_mode == HVAC_MODE_OFF:
            payload_off = {
                "requests": [
                    {
                        "op": 3,
                        "to": "/dsiot/edge/adr_0100.dgc_status",
                        "pc": {
                            "pn": "dgc_status",
                            "pch": [
                                {
                                    "pn": "e_1002",
                                    "pch": [
                                        {
                                            "pn": "e_A002",
                                            "pch": [{"pn": "p_01", "pv": "00"}],
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ]
            }
            url = f"http://{self.host}/dsiot/multireq"
            session = async_get_clientsession(self.hass)
            try:
                async with session.put(
                    url, json=payload_off, headers={"Content-Type": "application/json"}
                ) as resp:
                    resp.raise_for_status()
                    _LOGGER.info("Climate: set HVAC_MODE OFF (power=00)")
            except Exception as e:
                _LOGGER.error("Climate: error setting OFF: %s", e)

            await self.coordinator.async_request_refresh()
            return

        # If not OFF, map and set mode + ensure power=01
        mode_hex = MODE_REVERSE_MAP.get(hvac_mode)
        if mode_hex is None:
            _LOGGER.warning("Climate: unsupported hvac_mode '%s'", hvac_mode)
            return

        payload = {
            "requests": [
                {
                    "op": 3,
                    "to": "/dsiot/edge/adr_0100.dgc_status",
                    "pc": {
                        "pn": "dgc_status",
                        "pch": [
                            {
                                "pn": "e_1002",
                                "pch": [{"pn": "e_A002", "pch": [{"pn": "p_01", "pv": "01"}]}],
                            }
                        ],
                    },
                },
                {
                    "op": 3,
                    "to": "/dsiot/edge/adr_0100.dgc_status",
                    "pc": {
                        "pn": "dgc_status",
                        "pch": [
                            {
                                "pn": "e_1002",
                                "pch": [{"pn": "e_3001", "pch": [{"pn": "p_01", "pv": mode_hex}]}],
                            }
                        ],
                    },
                },
            ]
        }

        url = f"http://{self.host}/dsiot/multireq"
        session = async_get_clientsession(self.hass)
        try:
            async with session.put(
                url, json=payload, headers={"Content-Type": "application/json"}
            ) as resp:
                resp.raise_for_status()
                _LOGGER.info("Climate: set HVAC_MODE to %s (hex=%s)", hvac_mode, mode_hex)
        except Exception as e:
            _LOGGER.error("Climate: error setting hvac_mode %s: %s", hvac_mode, e)

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs) -> None:
        """
        Set a new target temperature (°C).
        HA calls with kwargs={"temperature": <float>}. We clamp to [16.0,30.0],
        convert to raw_value=int(temp×2), pack LE, hex­encode, and send under
        e_1002 → e_3001 → p_03 → pv.
        """
        if (temp := kwargs.get("temperature")) is None:
            return

        if temp < MIN_TEMP:
            temp = MIN_TEMP
        elif temp > MAX_TEMP:
            temp = MAX_TEMP

        raw_value = int(round(temp * 2))
        raw_bytes = raw_value.to_bytes(2, byteorder="little", signed=False)
        hexstr = raw_bytes.hex().upper()

        payload = {
            "requests": [
                {
                    "op": 3,
                    "to": "/dsiot/edge/adr_0100.dgc_status",
                    "pc": {
                        "pn": "dgc_status",
                        "pch": [
                            {
                                "pn": "e_1002",
                                "pch": [{"pn": "e_3001", "pch": [{"pn": "p_03", "pv": hexstr}]}],
                            }
                        ],
                    },
                }
            ]
        }

        url = f"http://{self.host}/dsiot/multireq"
        session = async_get_clientsession(self.hass)
        try:
            async with session.put(
                url, json=payload, headers={"Content-Type": "application/json"}
            ) as resp:
                resp.raise_for_status()
                _LOGGER.info("Climate: set temperature to %.1f°C (hex=%s)", temp, hexstr)
        except Exception as e:
            _LOGGER.error("Climate: error setting temperature: %s", e)

        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """
        Set a new fan mode. HA calls with fan_mode ∈ {"1","2","3","4","5","Auto","Quiet"}.
        We look up the correct hex code via FAN_SPEED_REVERSE_MAP and send under
        e_1002 → e_3001 → p_0A → pv.
        """
        if fan_mode not in FAN_SPEED_REVERSE_MAP:
            _LOGGER.warning("Climate: fan_mode '%s' not supported", fan_mode)
            return

        hexcode = FAN_SPEED_REVERSE_MAP[fan_mode]

        payload = {
            "requests": [
                {
                    "op": 3,
                    "to": "/dsiot/edge/adr_0100.dgc_status",
                    "pc": {
                        "pn": "dgc_status",
                        "pch": [
                            {
                                "pn": "e_1002",
                                "pch": [{"pn": "e_3001", "pch": [{"pn": "p_0A", "pv": hexcode}]}],
                            }
                        ],
                    },
                }
            ]
        }

        url = f"http://{self.host}/dsiot/multireq"
        session = async_get_clientsession(self.hass)
        try:
            async with session.put(
                url, json=payload, headers={"Content-Type": "application/json"}
            ) as resp:
                resp.raise_for_status()
                _LOGGER.info("Climate: set fan_mode to %s (hex=%s)", fan_mode, hexcode)
        except Exception as e:
            _LOGGER.error("Climate: error setting fan_mode: %s", e)

        await self.coordinator.async_request_refresh()

    def _get_power_value(self) -> str:
        """
        Helper to read the “power” PV (On/Off) from coordinator.data:
          e_1002 → e_A002 → [0] → pv.
        Returns "00" or "01" (defaults to "00" on error).
        """
        try:
            node = self.coordinator.data
            level1 = next(item for item in node if item.get("pn") == "e_1002")
            level2 = next(item for item in level1.get("pch", []) if item.get("pn") == "e_A002")
            return level2.get("pch", [])[0].get("pv", "00")
        except Exception:
            return "00"
