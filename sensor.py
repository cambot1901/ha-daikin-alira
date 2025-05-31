from datetime import timedelta
import logging
import asyncio
import async_timeout
import aiohttp

from homeassistant.components.sensor import SensorEntity
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}-{host}",
        update_method=lambda: fetch_status(session, host),
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            DaikinSetpointSensor(coordinator),
            DaikinIndoorTempSensor(coordinator),
            DaikinIndoorHumiditySensor(coordinator),
            DaikinFanSpeedSensor(coordinator),
            DaikinModeSensor(coordinator),
            DaikinPowerSensor(coordinator),
        ],
        True,
    )


async def fetch_status(session: aiohttp.ClientSession, host: str) -> dict:
    url = f"http://{host}/dsiot/multireq"
    payload = {"requests": [{"op": 2, "to": "/dsiot/edge/adr_0100.dgc_status"}]}
    try:
        async with async_timeout.timeout(10):
            async with session.post(url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
        return data["responses"][0]["pc"]["pch"]
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError) as e:
        _LOGGER.error("Failed to fetch data from %s: %s", host, e)
        return []


class BaseDaikinSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, name: str, unique_suffix: str):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{coordinator.name}_{unique_suffix}"

    @property
    def native_value(self):
        return self._get_value(self.coordinator.data)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.name)},
            "name": "Daikin Alira",
            "manufacturer": "Daikin",
            "model": "Alira",
        }

    def _get_by_path(self, data, *path_segments):
        node = data
        try:
            for seg in path_segments:
                node = next(item for item in node if item.get("pn") == seg).get("pch", [])
            return node
        except (StopIteration, AttributeError, TypeError):
            _LOGGER.warning("Failed to find path: %s", " → ".join(path_segments))
            return []

    def _parse_hex_to_int(self, hexstr, scale=1):
        try:
            return int.from_bytes(bytes.fromhex(hexstr), "little") / scale
        except Exception:
            _LOGGER.warning("Invalid hex string: %s", hexstr)
            return None


class DaikinSetpointSensor(BaseDaikinSensor):
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator):
        super().__init__(coordinator, "Setpoint Temperature", "setpoint")

    def _get_value(self, data):
        path = self._get_by_path(data, "e_1002", "e_3001")
        if len(path) >= 3:
            return self._parse_hex_to_int(path[2].get("pv", ""), scale=2)
        return None


class DaikinIndoorTempSensor(BaseDaikinSensor):
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator):
        super().__init__(coordinator, "Indoor Temperature", "indoor_temp")

    def _get_value(self, data):
        path = self._get_by_path(data, "e_1002", "e_A00B")
        if path:
            return self._parse_hex_to_int(path[0].get("pv", ""))
        return None


class DaikinIndoorHumiditySensor(BaseDaikinSensor):
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator):
        super().__init__(coordinator, "Indoor Humidity", "indoor_humidity")

    def _get_value(self, data):
        path = self._get_by_path(data, "e_1002", "e_A00B")
        if len(path) > 1:
            return self._parse_hex_to_int(path[1].get("pv", ""))
        return None


class DaikinFanSpeedSensor(BaseDaikinSensor):
    FAN_SPEED_MAP = {
        "0300": "1", "0400": "2", "0500": "3", "0600": "4", "0700": "5",
        "0A00": "Auto", "0B00": "Quiet"
    }

    def __init__(self, coordinator):
        super().__init__(coordinator, "Fan Speed", "fan_speed")

    def _get_value(self, data):
        path = self._get_by_path(data, "e_1002", "e_3001")
        if len(path) >= 9:
            hexstr = path[8].get("pv", "")
            return self.FAN_SPEED_MAP.get(hexstr, f"Unknown ({hexstr})")
        return None


class DaikinModeSensor(BaseDaikinSensor):
    MODE_MAP = {
        "0300": "Auto", "0200": "Cool", "0100": "Heat", "0000": "Fan", "0500": "Dry"
    }

    def __init__(self, coordinator):
        super().__init__(coordinator, "Operation Mode", "mode")

    def _get_value(self, data):
        path = self._get_by_path(data, "e_1002", "e_3001")
        if path:
            hexstr = path[0].get("pv", "")
            return self.MODE_MAP.get(hexstr, f"Unknown ({hexstr})")
        return None


class DaikinPowerSensor(BaseDaikinSensor):
    POWER_MAP = {"00": "Off", "01": "On"}

    def __init__(self, coordinator):
        super().__init__(coordinator, "Power State", "power")

    def _get_value(self, data):
        path = self._get_by_path(data, "e_1002", "e_A002")
        if path:
            hexstr = path[0].get("pv", "")
            return self.POWER_MAP.get(hexstr, f"Unknown ({hexstr})")
        return None
