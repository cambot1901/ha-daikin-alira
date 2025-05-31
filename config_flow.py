"""Config flow for Daikin Alira integration."""
import voluptuous as vol
import aiohttp
from homeassistant import config_entries
from .const import DOMAIN, CONF_HOST

class DaikinAliraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Daikin Alira."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://{host}/") as resp:
                        if resp.status != 200:
                            raise Exception("Unexpected response")
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"Daikin @ {host}", data=user_input)

        data_schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
