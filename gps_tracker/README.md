# GPS Tracker

Reads NMEA sentences from a USB GPS receiver and publishes a `device_tracker` entity in Home Assistant with full telemetry: position, altitude, speed, heading, satellite count, fix quality, and accuracy estimate.

## Requirements

- A USB GPS receiver that exposes a serial port (e.g. u-blox, SiRF, MTK-based)
- Common device paths: `/dev/ttyACM0`, `/dev/ttyUSB0`, or a stable symlink under `/dev/serial/by-id/`

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `device` | device | `/dev/ttyACM0` | Serial port of the GPS receiver. Use the device picker to select from available ports. |
| `baud` | int | `9600` | Baud rate of the GPS receiver. Most receivers default to 9600. |
| `entity_name` | str | `gps_vehicle` | Name of the `device_tracker` entity created in HA (`device_tracker.<entity_name>`). |
| `update_interval` | int | `5` | Minimum time in seconds between state updates. |
| `min_distance` | int | `10` | Minimum movement in meters before sending an update. Set to `0` to send every interval regardless of movement. Useful to reduce noise from stationary GPS jitter. |
| `log_level` | select | `info` | Log verbosity: `debug`, `info`, `warning`, `error`, `critical`. |

## Home Assistant Entity

The add-on creates a single entity:

```
device_tracker.<entity_name>
```

### Attributes

| Attribute | Source | Description |
|-----------|--------|-------------|
| `latitude` | GGA / RMC | Latitude in decimal degrees |
| `longitude` | GGA / RMC | Longitude in decimal degrees |
| `altitude` | GGA | Altitude in metres above mean sea level |
| `speed` | VTG / RMC | Speed over ground in km/h |
| `heading` | VTG / RMC | True heading in degrees |
| `satellites_used` | GGA | Number of satellites used in fix |
| `satellites_visible` | GSV | Total satellites visible |
| `hdop` | GGA / GSA | Horizontal dilution of precision |
| `vdop` | GSA | Vertical dilution of precision |
| `pdop` | GSA | Position dilution of precision |
| `fix_type` | GSA | `no_fix`, `2D_fix`, or `3D_fix` |
| `fix_quality` | GGA | `GPS`, `DGPS`, `RTK_fixed`, `RTK_float` |
| `gps_accuracy` | computed | Estimated accuracy in metres (`HDOP × 5`) |
| `source_type` | — | Always `gps` |

## Notes

- The entity state is `not_home` when a fix is available, `home` when no position data is received.
- The `min_distance` filter compares against the last **sent** position, not the last GPS reading. On restart, the add-on reads the last known position from HA to avoid a spurious first update.
- The add-on reconnects automatically if the serial port is lost (e.g. USB unplug/replug).