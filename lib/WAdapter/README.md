# WAdapter (vendored)

ESP8266 network and device support used by [WThermostatBeca-labo](../../README.md). This copy is maintained with the thermostat firmware and is not a separately released library.

It provides:

- Device properties, local web configuration, MQTT and WebThings access.
- Wi-Fi reconnection with optional BSSID locking and a recovery AP after persistent network faults.
- Static IPv4 validation and local gateway checks without depending on Internet access or MQTT availability.
- Optional administrator login, UTF-8 HTTP Digest, configuration form protection and firmware uploads.
- Wi-Fi passwords up to 63 bytes or a 64-digit hexadecimal PSK, preserving legacy configuration field offsets.
- A five-minute local login recovery window when the thermostat MCU requests Wi-Fi setup from its panel. Automatic fallback does not bypass login.

The thermostat application connects its MCU setup callback to local recovery; WAdapter does not require buttons wired to the ESP8266. Minimal bridge builds omit the thermostat MCU integration.

See the main [setup and recovery instructions](../../README.md#administration-and-security), [build instructions](../../README.md#build-and-test) and [GitHub Releases](https://github.com/labodj/WThermostatBeca-labo/releases) for supported firmware versions and downloads. Tests and build dependencies are managed at the repository root.
