"""The Daikin Alira integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via YAML (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up Daikin Alira from a config entry.

    Forward the entry separately to each platform (sensor & climate)
    because async_setup_platforms() is not supported on this HA version.
    """
    # Forward to sensor platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, PLATFORMS[0])
    )
    # Forward to climate platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, PLATFORMS[1])
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a config entry.

    Unload each platform (sensor & climate) individually.
    """
    # Unload sensor
    await hass.config_entries.async_forward_entry_unload(entry, PLATFORMS[0])
    # Unload climate
    await hass.config_entries.async_forward_entry_unload(entry, PLATFORMS[1])
    return True
