# WAdapter (vendored)

ESP8266 network and device support used by [WThermostatBeca-labo](../../README.md). This copy is maintained with the thermostat firmware and is not a separately released library.

It provides:

- Device properties, local web configuration, MQTT and WebThings access.
- Wi-Fi reconnection with optional BSSID locking and a recovery AP after persistent network faults.
- Static IPv4 validation and local gateway checks without depending on Internet access or MQTT availability.
- Optional administrator login, UTF-8 HTTP Digest, configuration form protection and firmware uploads.
- Wi-Fi passwords up to 63 bytes or a 64-digit hexadecimal PSK, preserving legacy configuration field offsets.
- A five-minute local login recovery window when the thermostat MCU requests Wi-Fi setup from its panel. Automatic fallback does not bypass login.

Static web assets borrow their PROGMEM data instead of copying whole bodies into RAM. HTML responses use bounded 256-byte blocks, released as the transport consumes them. Admission checks total free memory separately from the smaller contiguous-block requirement; callers handle rejected or failed allocations. Asset requests use a smaller reserve than full pages, so a cold browser cache can load CSS and JavaScript alongside the page.

HTML rendering releases request headers after authentication and origin checks. Admission includes an 8 KiB margin beyond the estimated page size for transport and other requests. Concurrent large pages can therefore receive HTTP 503; retry after the other transfer finishes. TCP abort detaches the client before invoking callbacks that may destroy it.

Flash asset admission reserves 1 KiB for response objects and headers, not a full transport window. The library uses its standard two-MSS send buffer. Its allocation is checked, and transport retries later when memory is unavailable. Core POST forms carry a server-generated CSRF token, including Home buttons and Live WebLog actions; GET forms carry none. Form protection does not depend on JavaScript.

ESPAsyncWebServer is pinned to official commit `136daa499d2cf1962909304b83b9666740a070b6`. Transport integration tests extract the installed library's send routine and verify exact bytes and completion under bounded TCP space and empty-source retries. Register the global WebLog handler by reference: its lifetime belongs to the application, not to a server instance.

The unreleased source also checks boot-local Digest challenges, request targets and nonce counters, including parallel requests. JSON and HTML responses use `WCheckedPrint` with an 8 KiB limit. HTML page callbacks receive this checked writer instead of the underlying response stream. Formatting failures, short writes and oversized responses invalidate the response; a failed page is discarded before sending HTTP 503. `WPageResponse` avoids a contiguous 6 KiB network-form allocation and copy-before-free growth; the complete page is validated before any successful response is sent. Live WebLog skips messages below an 8 KiB largest-free-block reserve or when a client queue is full; the build caps queues at four messages. MQTT logging is independent of WebLog backpressure.

Configuration forms use `WSettings::beginUpdate()` / `endUpdate()` to batch registered settings and extension records in one EEPROM session. Setters do not autosave during that session. A failed or cancelled update restores the previous property values in RAM; callers must check the result before reporting success or rebooting. A reported write failure blocks autosaves until a complete recovery save succeeds. Legacy storage offsets are unchanged. This reduces flash wear but does not make the single physical flash sector power-loss atomic.

Property subclasses with additional constraints override `isValidValue()` without checking writability or changing state. `canParse()` additionally enforces read-only status. This lets JSON batches validate all known values before callbacks can change which properties are writable.

The thermostat application connects its MCU setup callback to local recovery; WAdapter does not require buttons wired to the ESP8266. Minimal bridge builds omit the thermostat MCU integration.

See the main [setup and recovery instructions](../../README.md#administration-and-security), [build instructions](../../README.md#build-and-test) and [GitHub Releases](https://github.com/labodj/WThermostatBeca-labo/releases) for supported firmware versions and downloads. Tests and build dependencies are managed at the repository root.

ESPAsyncWebServer is pinned to the official repository and ESPAsyncTCP to the labodj maintenance fork, both at full commit SHAs. Firmware builds do not patch dependency sources. When updating either SHA, rerun the transport tests and firmware builds.

The labodj/ESPAsyncTCP fork is based on official 2.0.0. Its issue 511 fix preserves the abort result when lwIP invokes a callback that destroys the client. The pinned TCP fork also leaves empty outputs pollable, so allocation failures can recover. Tests defer reading queued bytes until after callbacks return and exercise bounded TCP space, empty-source retries and allocation failures.

Partial writes are counted before deferring the remainder. Integration tests cover exact delivery across partial writes, temporary allocation failures and pending TCP output.

Queued TCP data is retried from polling after temporary output failures, even with a full send queue. Accepted byte counts reflect queued bytes, preventing duplicate resubmission. Persistent output failures retain the timeout. Experimental per-connection TCP snapshots and global counters are not included in normal firmware.

The TCP lifetime, byte-count and output-retry fixes live in the versioned TCP dependency. The server integration branch also includes the ESP8266 header-allocation guard.
