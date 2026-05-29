# Changelog

## 0.2.2

- Remove icon option (no native icon picker in addon schema)

## 0.2.1

- Add icon option (reverted in 0.2.2)

## 0.2.0

- Add icon and logo
- Add UI translations: English, French, German, Spanish, Italian
- Fix addon URL and slug in config

## 0.1.9

- Add `min_distance` filter to avoid posting GPS noise when stationary
- Read last known position from HA on startup to initialize the filter
- Refactor API helpers (`_headers`, `get_last_position`)

## 0.1.8

- Remove unused `hassio_api` permission

## 0.1.7 — 0.1.4

- Fix `SUPERVISOR_TOKEN` not injected: use `/usr/bin/with-contenv` as CMD wrapper
- Add `log_level` option (debug / info / warning / error / critical)
- Fix serial port reconnection: reopen port on each retry instead of reusing broken handle
- Add `homeassistant_api: true` permission for HA Core API access

## 0.1.1

- Add `device` schema type for visual device picker in HA UI
- Switch base image to `ghcr.io/home-assistant/aarch64-base:3.19` + apk Python

## 0.1.0

- Initial release
- Reads GGA, RMC, VTG, GSA, GSV NMEA sentences
- Publishes `device_tracker` entity with full telemetry