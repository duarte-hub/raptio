# raptio

A small headless container that polls the KegLand [RAPT](https://rapt.io) cloud API and publishes
your devices to MQTT with Home Assistant auto-discovery.

Based on [MetalOctopus/RAPT-to-MQTT](https://github.com/MetalOctopus/RAPT-to-MQTT), stripped down
to the poller: no web UI, no database, no Tilt handling. Configuration is environment variables only.

## What you get in Home Assistant

Each RAPT device appears as its own device, with whichever of these the API reports for it:

| Entity | Notes |
|---|---|
| Temperature, Target temperature | °C |
| Gravity, Gravity velocity | RAPT Pill; gravity normalised to SG (1.048) |
| Battery, Signal | diagnostic |
| Cooling, Heating | inferred from the controller's runtime counters advancing between polls, so they lag by one poll |
| Connection | whether RAPT sees the device as connected |

Polled device types: temperature controllers, Pill hydrometers, fermentation chambers, BrewZillas,
stills and bonded BLE devices. The full API record for each device (minus telemetry history) is
published as JSON to `rapt2mqtt/<device id>/state`, so you can template anything else out of it.

Read-only: it does not set target temperatures.

## Run

1. In the RAPT portal, create an API secret under **My Account > API Secrets**.
2. Copy `.env.example` to `.env` and fill it in.
3. `docker compose up -d`

Home Assistant needs the MQTT integration with discovery enabled (the default).

## Configuration

| Variable | Default | |
|---|---|---|
| `RAPT_EMAIL` | required | RAPT portal login |
| `RAPT_SECRET` | required | API secret, not your password |
| `MQTT_HOST` | required | |
| `MQTT_PORT` | `1883` | |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | empty | |
| `POLL_INTERVAL` | `300` | seconds, minimum 60 |
| `BASE_TOPIC` | `rapt2mqtt` | |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | |
| `LOG_LEVEL` | `INFO` | |

Entities go unavailable if the container stops, or if the RAPT API stops answering for three
poll intervals.

## Image

Built for `linux/amd64` and `linux/arm64` by GitHub Actions on every push to `main` and published
to `ghcr.io/duarte-hub/raptio`.
