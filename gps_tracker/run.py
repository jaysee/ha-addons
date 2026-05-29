#!/usr/bin/env python3
import json
import logging
import math
import os
import time

import pynmea2
import requests
import serial

log = logging.getLogger("gps_tracker")

OPTIONS_FILE = "/data/options.json"
HA_API = "http://supervisor/core/api"
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

FIX_TYPES = {0: "no_fix", 1: "2D_fix", 2: "3D_fix", 6: "estimated"}
FIX_QUALITY = {0: "invalid", 1: "GPS", 2: "DGPS", 4: "RTK_fixed", 5: "RTK_float"}


def load_options():
    with open(OPTIONS_FILE) as f:
        return json.load(f)


def _headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def get_last_position(entity_id):
    try:
        r = requests.get(f"{HA_API}/states/device_tracker.{entity_id}", headers=_headers(), timeout=5)
        if r.status_code == 200:
            attrs = r.json().get("attributes", {})
            lat, lon = attrs.get("latitude"), attrs.get("longitude")
            if lat is not None and lon is not None:
                return float(lat), float(lon)
    except Exception:
        pass
    return None, None


def post_state(entity_id, attributes):
    url = f"{HA_API}/states/device_tracker.{entity_id}"
    state = "home" if attributes.get("latitude") is None else "not_home"
    try:
        r = requests.post(url, json={"state": state, "attributes": attributes}, headers=_headers(), timeout=5)
        r.raise_for_status()
    except Exception as e:
        log.warning("Failed to post state: %s", e)


def safe_float(value):
    try:
        v = float(value)
        return v if v != 0.0 else None
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def knots_to_kmh(knots):
    v = safe_float(knots)
    return round(v * 1.852, 1) if v is not None else None


def distance_m(lat1, lon1, lat2, lon2):
    dlat = (lat2 - lat1) * 111_000
    dlon = (lon2 - lon1) * 111_000 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.sqrt(dlat ** 2 + dlon ** 2)


def main():
    opts = load_options()
    device = opts["device"]
    baud = opts["baud"]
    entity_name = opts.get("entity_name", "gps_vehicle")
    update_interval = opts.get("update_interval", 5)
    min_distance = opts.get("min_distance", 10)
    log_level = opts.get("log_level", "info").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    log.info("Opening %s at %d baud", device, baud)

    # Accumulated state from multiple NMEA sentences
    gps = {
        "latitude": None,
        "longitude": None,
        "altitude": None,       # metres, from GGA
        "speed": None,          # km/h, from VTG or RMC
        "heading": None,        # degrees true, from VTG or RMC
        "satellites_used": None,  # from GGA
        "satellites_visible": None,  # from GSV
        "hdop": None,           # from GGA
        "vdop": None,           # from GSA
        "pdop": None,           # from GSA
        "fix_type": None,       # 2D / 3D / no_fix, from GSA
        "fix_quality": None,    # GPS / DGPS / RTK, from GGA
        "gps_accuracy": None,   # metres (estimated from HDOP)
        "source_type": "gps",
    }

    last_post = 0.0
    last_lat, last_lon = get_last_position(entity_name)
    if last_lat is not None:
        log.info("Resumed from last known position: %.6f, %.6f", last_lat, last_lon)

    while True:
        try:
            with serial.Serial(device, baud, timeout=1) as ser:
                log.info("Serial open — reading NMEA sentences")
                while True:
                    raw = ser.readline().decode("ascii", errors="replace").strip()
                    if not raw.startswith("$"):
                        continue

                    try:
                        msg = pynmea2.parse(raw)
                    except pynmea2.ParseError:
                        continue

                    sentence = type(msg).__name__

                    # GGA — position, altitude, fix quality, satellites, HDOP
                    if sentence == "GGA":
                        lat = safe_float(msg.latitude)
                        lon = safe_float(msg.longitude)
                        if lat and lon:
                            gps["latitude"] = round(lat, 7)
                            gps["longitude"] = round(lon, 7)
                        gps["altitude"] = safe_float(msg.altitude)
                        gps["satellites_used"] = safe_int(msg.num_sats)
                        gps["hdop"] = safe_float(msg.horizontal_dil)
                        qual = safe_int(msg.gps_qual)
                        gps["fix_quality"] = FIX_QUALITY.get(qual, str(qual)) if qual is not None else None
                        if gps["hdop"]:
                            gps["gps_accuracy"] = round(gps["hdop"] * 5, 1)

                    # RMC — speed and heading (fallback if no VTG)
                    elif sentence == "RMC":
                        lat = safe_float(msg.latitude)
                        lon = safe_float(msg.longitude)
                        if lat and lon:
                            gps["latitude"] = round(lat, 7)
                            gps["longitude"] = round(lon, 7)
                        if gps["speed"] is None:
                            gps["speed"] = knots_to_kmh(msg.spd_over_grnd)
                        if gps["heading"] is None:
                            gps["heading"] = safe_float(msg.true_course)

                    # VTG — speed and heading (preferred, more accurate)
                    elif sentence == "VTG":
                        gps["speed"] = safe_float(msg.spd_over_grnd_kmph)
                        gps["heading"] = safe_float(msg.true_track)

                    # GSA — fix type (2D/3D), PDOP, HDOP, VDOP
                    elif sentence == "GSA":
                        mode = safe_int(msg.mode_fix_type)
                        gps["fix_type"] = FIX_TYPES.get(mode)
                        gps["pdop"] = safe_float(msg.pdop)
                        if gps["hdop"] is None:
                            gps["hdop"] = safe_float(msg.hdop)
                        gps["vdop"] = safe_float(msg.vdop)

                    # GSV — total satellites visible
                    elif sentence == "GSV":
                        gps["satellites_visible"] = safe_int(msg.num_sv_in_view)

                    now = time.time()
                    if now - last_post >= update_interval and gps["latitude"] is not None:
                        moved = (
                            last_lat is None
                            or min_distance == 0
                            or distance_m(last_lat, last_lon, gps["latitude"], gps["longitude"]) >= min_distance
                        )
                        if moved:
                            attrs = {k: v for k, v in gps.items() if v is not None}
                            attrs["friendly_name"] = entity_name.replace("_", " ").title()
                            post_state(entity_name, attrs)
                            log.info(
                                "lat=%.6f lon=%.6f alt=%sm speed=%skm/h heading=%s° sats=%s/%s fix=%s",
                                gps["latitude"],
                                gps["longitude"],
                                gps["altitude"],
                                gps["speed"],
                                gps["heading"],
                                gps["satellites_used"],
                                gps["satellites_visible"],
                                gps["fix_type"],
                            )
                            last_lat = gps["latitude"]
                            last_lon = gps["longitude"]
                        else:
                            log.debug("Position inchangée (< %dm), pas d'envoi", min_distance)
                        # Reset RMC fallbacks so VTG takes priority next cycle
                        gps["speed"] = None
                        gps["heading"] = None
                        last_post = now

        except serial.SerialException as e:
            log.error("Serial error: %s — reopening in 5s", e)
            time.sleep(5)
        except Exception as e:
            log.exception("Unexpected error: %s", e)
            time.sleep(1)


if __name__ == "__main__":
    main()
