DAIKIN ALIRA HOME ASSISTANT INTEGRATION
A custom Home Assistant integration to control and monitor Daikin Alira air conditioners over HTTP. This integration provides:

Sensors for:
  - Setpoint Temperature
  - Indoor Temperature
  - Indoor Humidity
  - Fan Speed
  - Operation Mode
  - Power State

Climate entity with full control:
  - On/Off
  - Target Temperature (16 to 30 °C in 0.5 °C increments)
  - Fan Modes (1, 2, 3, 4, 5, Auto, Quiet)
  - Operation Modes (Auto, Cool, Heat, Fan only, Dry)

REPOSITORY STRUCTURE

custom_components/daikin_alira/
  init.py (Sets up the integration and forwards entries to sensor and climate platforms)
  manifest.json (Integration metadata)
  const.py (Constants, including integration domain and configuration keys)
  config_flow.py (Enables configuration via UI; asks only for host)
  sensor.py (Defines sensor entities and data-fetch logic)
  climate.py (Defines a ClimateEntity for full AC control: On/Off, temperature, fan, mode)
  logo.png (optional) (128x128 PNG for integration icon)
  README.md (This file)

FEATURES
  Sensors
    Entity                         Description                             Unit
    sensor.daikin_alira_setpoint   Current setpoint temperature            °C
    sensor.daikin_alira_temp       Indoor temperature                      °C
    sensor.daikin_alira_humidity   Indoor humidity                         %
    sensor.daikin_alira_fan_speed  Fan speed (values 1 to 5, Auto, Quiet)  N/A
    sensor.daikin_alira_mode       Operation mode (Auto, Cool, Heat,       N/A
                                   Fan only, Dry)
    sensor.daikin_alira_power      Power state (On or Off)                 N/A

Data is polled every 30 seconds. All sensors share a single DataUpdateCoordinator to minimize HTTP requests.

Climate
Entity Description
  - climate.daikin_alira_<host> Full AC control with On/Off, temperature, fan, mode

Supported Features
  - On/Off : Turn the AC on or off.
  - Target Temperature : Setpoint range 16 °C to 30 °C in 0.5 °C increments.
  - Fan Modes : Select fan speeds 1-5, Auto, or Quiet.
  - Operation Modes : Auto, Cool, Heat, Fan only, Dry.

Commands are sent over HTTP to the /dsiot/multireq endpoint on the Daikin unit.

INSTALLATION

Copy this folder into your Home Assistant custom_components directory:
/config/custom_components/daikin_alira/

Restart Home Assistant.

In the Home Assistant UI, go to Settings, then Integrations, click the plus sign (+), and search for Daikin Alira.
Enter the IP address or hostname of your Daikin Alira unit.
Click Submit. Sensors and the Climate entity will be created automatically.
Optionally, add logo.png (128x128 PNG) to the folder for a custom integration icon.

CONFIGURATION
After installation:
  Go to Settings, then Devices & Services, then Integrations.
  Find Daikin Alira, click Configure, and enter:

Host: The IP address or hostname of your Daikin unit.

The integration will set up automatically. You will see:
A device named “Daikin Alira” with all related sensors.
A Climate entity named “Daikin AC”.

YAML (Advanced)

This integration is meant to be configured via the UI. YAML configuration is not required. However, if you wish to configure via YAML, add the following to your configuration.yaml:

daikin_alira:
host: 192.168.1.123 # Replace with your device IP

Then remove any UI-based configuration for this integration to avoid duplicates.

USAGE

Lovelace Cards
  - Sensors appear as individual entities (temperature, humidity, fan speed, etc.).

The Climate entity appears as a thermostat card with:
  - On/Off toggle.
  - Target temperature slider (16 °C–30 °C).
  - Fan mode dropdown (1–5, Auto, Quiet).
  - Operation mode dropdown (Auto, Cool, Heat, Fan only, Dry).

Device Page
  All sensors and the Climate entity share a single device under Settings, Devices & Services, Devices. You can view and organize them there.

TROUBLESHOOTING

If you see two devices (one with sensors and another empty one), ensure that both sensor.py and climate.py use the exact same device_info "identifiers" tuple (DOMAIN, "daikin_alira-<host>"). Otherwise, Home Assistant will treat them as separate devices.

For network or timeout issues, verify that Home Assistant can reach the Daikin unit’s IP address. No firewall should block it. You can increase the timeout in sensor.py by adjusting the async_timeout setting if needed.

This integration assumes the Daikin unit’s HTTP endpoint is http://<host>/dsiot/multireq. If your unit requires HTTPS or a different endpoint path, you must edit fetch_status and the payload URLs accordingly.

Check Home Assistant logs (Developer Tools, Logs) for errors from custom_components/daikin_alira. Common issues include:

Invalid JSON responses.
Incorrect host/IP.
Unsupported hex codes.

DEVELOPMENT

Clone this repository into your local custom_components folder.

Key entry points:
sensor.py : Creates DataUpdateCoordinator, fetches status, defines sensors.
climate.py: Defines DaikinClimate and handles HVAC commands (set_hvac_mode, set_temperature, set_fan_mode).
config_flow.py: Provides a minimal UI for entering the host.

CREDITS
Author: @cambot1901
This integration follows Home Assistant’s ClimateEntity and CoordinatorEntity patterns.
Feel free to open issues or submit pull requests on GitHub.

Last updated: May 31, 2025
