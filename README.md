# raptio

Gets your KegLand [RAPT](https://rapt.io) brewing devices into Home Assistant by polling the RAPT
cloud API. There are two ways to run it; pick one:

- **Home Assistant integration (HACS)**: runs inside HA, set up from the UI, no MQTT needed.
- **Docker container**: a headless poller that publishes to MQTT with HA auto-discovery.

Running both against the same account just doubles your API calls.

Based on [MetalOctopus/RAPT-to-MQTT](https://github.com/MetalOctopus/RAPT-to-MQTT), stripped down
to the poller: no web UI, no database, no Tilt handling. Read-only: it does not set target
temperatures.

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
stills and bonded BLE devices.

Either way you need an API secret: in the RAPT portal, go to **My Account > API Secrets** and
create one. It is not your account password.

## Option 1: Home Assistant integration (HACS)

1. In HACS, open the menu > **Custom repositories**, add `https://github.com/duarte-hub/raptio`
   with type **Integration**.
2. Install **RAPT Cloud** and restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration**, search for **RAPT Cloud**, and enter
   your RAPT email, API secret and poll interval.

The poll interval (default 300 s, minimum 60 s) can be changed later with **Configure** on the
integration. If RAPT starts rejecting the secret, HA prompts you to enter a new one.

## Option 2: Docker container (MQTT)

1. Copy `.env.example` to `.env` and fill it in.
2. `docker compose up -d`

Home Assistant needs the MQTT integration with discovery enabled (the default).

| Variable | Default | |
|---|---|---|
| `RAPT_EMAIL` | required | RAPT portal login |
| `RAPT_SECRET` | required | API secret, not your password |
| `MQTT_HOST` | required | |
| `MQTT_PORT` | `1883` | |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | empty | |
| `MQTT_TLS` | `false` | verify against system CAs; use with port 8883. Without it, MQTT credentials travel in cleartext |
| `POLL_INTERVAL` | `300` | seconds, minimum 60 |
| `BASE_TOPIC` | `rapt2mqtt` | |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | |
| `LOG_LEVEL` | `INFO` | |

Each device's state is published as retained JSON to `rapt2mqtt/<device id>/state`. Only an
allowlist of fields (`STATE_FIELDS` in `rapt2mqtt.py`) is published, not the raw API record, which
also carries serial numbers and MAC addresses.

Entities go unavailable if the container stops, or if the RAPT API stops answering for three
poll intervals.

The image is built for `linux/amd64` and `linux/arm64` by GitHub Actions on every push to `main`
and published to `ghcr.io/duarte-hub/raptio`.
