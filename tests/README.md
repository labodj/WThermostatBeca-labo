# Firmware regression tests

Tests compile production headers or extract methods from the current source.
They use small host substitutes for Arduino, EEPROM, networking and the MCU;
they do not connect to thermostats. AddressSanitizer and UndefinedBehaviorSanitizer
check native C++ runs. Integration tests use the pinned transport sources.

Install the development requirements and PlatformIO dependencies first, as in
the project README. Run the entire suite on both host integer models:

```sh
python -m unittest discover -s tests -v
CXX="g++ -m32" python -m unittest discover -s tests -v
```

The second command requires the host's multilib C++ libraries. It is required
for 32-bit `long`, unsigned parsing and timer rollover cases; neither host model
replaces a build with the ESP8266 toolchain. CI runs both commands.

| Area | Tests |
| --- | --- |
| MCU startup, UART and control | `test_mcu_*`, `test_temperature_commands.py`, `test_resync.py` |
| Clock and schedules | `test_clock.py`, `test_documented_timezones.py`, `test_schedules.py` |
| Properties, parsing and serialization | `test_properties.py`, `test_parsers.py`, `test_json_output.py`, `test_runtime_contracts.py` |
| Storage and migration | `test_settings_failures.py`, `test_storage_layout.py`, `test_network_strings.py` |
| Wi-Fi and recovery | `test_wifi_bssid.py`, `test_bssid_runtime.py`, `test_network_recovery.py` |
| MQTT and discovery | `test_mqtt_delivery.py`, `test_homeassistant.py` |
| HTTP, authentication and UI | `test_http_requests.py`, `test_digest_auth.py`, `test_optional_auth.py`, `test_web*`, `test_page_response.py`, `test_html_reserve.py` |
| TCP dependency contracts | `test_async_transport.py`, `test_tcp_abort.py` |
| Build and development tools | `test_build_tools.py`, `test_analysis_tool.py`, `test_upload.py`, `test_argument_roles.py` |

`native_support.py` owns extraction and compilation helpers; `native/` contains
host API substitutes and reusable C++ cases. `render_ui.py` renders actual page
builders without contacting devices. For a focused run, use discovery with
`-p test_clock.py`, for example.

`homeassistant_schema.py` is a separate integration suite. Run it with the
isolated environment and pinned requirements described in the project README.
It validates emitted discovery against the official Home Assistant schemas.

Two old cases were removed because stronger retained cases cover their complete
assertions: legacy discovery IDs are checked in the discovery payload contract;
periodic publication rollover is checked together with the post-device-loop timer.
