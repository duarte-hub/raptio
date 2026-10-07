"""Poll the RAPT cloud API and publish devices to MQTT with Home Assistant discovery.

Headless, env-configured take on https://github.com/MetalOctopus/RAPT-to-MQTT.
"""

import json
import logging
import os
import re
import signal
import sys
import threading
import time

import paho.mqtt.client as mqtt
import requests

TOKEN_URL = "https://id.rapt.io/connect/token"
API_URL = "https://api.rapt.io/api/"

# List endpoint -> model name shown in the HA device registry
ENDPOINTS = {
    "TemperatureControllers/GetTemperatureControllers": "RAPT Temperature Controller",
    "Hydrometers/GetHydrometers": "RAPT Pill Hydrometer",
    "FermentationChambers/GetFermentationChambers": "RAPT Fermentation Chamber",
    "BrewZillas/GetBrewZillas": "BrewZilla",
    "Stills/GetStills": "RAPT Still",
    "BondedDevices/GetBondedDevices": "RAPT Bonded Device",
}

# Only these API fields are published; the raw record also carries serials, MAC
# addresses and account-level settings that have no business on the broker.
STATE_FIELDS = (
    "id", "name", "temperature", "targetTemperature", "tempUnit", "gravity", "gravityVelocity",
    "battery", "rssi", "connectionState", "lastActivityTime", "firmwareVersion",
    "coolingEnabled", "coolingRunTime", "heatingEnabled", "heatingRunTime", "pidEnabled",
)

MEASUREMENT = {"state_class": "measurement"}
DIAGNOSTIC = {"entity_category": "diagnostic"}

# An entity is only announced for a device whose state actually carries its key.
ENTITIES = [
    {"key": "temperature", "component": "sensor", "name": "Temperature",
     "config": {"device_class": "temperature", "unit_of_measurement": "°C", **MEASUREMENT}},
    {"key": "targetTemperature", "component": "sensor", "name": "Target temperature",
     "config": {"device_class": "temperature", "unit_of_measurement": "°C", **MEASUREMENT,
                "icon": "mdi:thermometer-chevron-up"}},
    {"key": "specific_gravity", "component": "sensor", "name": "Gravity",
     "config": {"unit_of_measurement": "SG", "suggested_display_precision": 3, **MEASUREMENT,
                "icon": "mdi:flask-outline"}},
    {"key": "gravityVelocity", "component": "sensor", "name": "Gravity velocity",
     "config": {"icon": "mdi:trending-down", **MEASUREMENT}},
    {"key": "battery", "component": "sensor", "name": "Battery",
     "config": {"device_class": "battery", "unit_of_measurement": "%", **MEASUREMENT, **DIAGNOSTIC}},
    {"key": "rssi", "component": "sensor", "name": "Signal",
     "config": {"device_class": "signal_strength", "unit_of_measurement": "dBm", **MEASUREMENT,
                **DIAGNOSTIC}},
    {"key": "cooling_active", "component": "binary_sensor", "name": "Cooling",
     "config": {"device_class": "running", "icon": "mdi:snowflake"}},
    {"key": "heating_active", "component": "binary_sensor", "name": "Heating",
     "config": {"device_class": "running", "icon": "mdi:fire"}},
    {"key": "connectionState", "component": "binary_sensor", "name": "Connection",
     "template": "{{ 'ON' if value_json.connectionState == 'Connected' else 'OFF' }}",
     "config": {"device_class": "connectivity", **DIAGNOSTIC}},
]

log = logging.getLogger("rapt2mqtt")


def sanitize(value):
    return re.sub(r"[^a-z0-9]", "_", str(value).lower())


class Bridge:
    def __init__(self, cfg, client, session=None):
        self._cfg = cfg
        self._client = client
        self._session = session or requests.Session()
        self._token = None
        self._token_expiry = 0
        self._runtimes = {}  # device id -> (coolingRunTime, heatingRunTime)
        self._announced = set()  # (device id, entity key)

    @property
    def status_topic(self):
        return f"{self._cfg['base_topic']}/status"

    def reset_discovery(self):
        """Forget what was announced so configs are re-sent (e.g. after a reconnect)."""
        self._announced.clear()

    # --- RAPT API ---

    def _get_token(self):
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        log.info("Requesting new RAPT API token...")
        r = self._session.post(TOKEN_URL, timeout=30, data={
            "client_id": "rapt-user",
            "grant_type": "password",
            "username": self._cfg["rapt_email"],
            "password": self._cfg["rapt_secret"],
        })
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + int(body.get("expires_in", 3600))
        return self._token

    def _get(self, endpoint, token):
        r = self._session.get(API_URL + endpoint, timeout=30, headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        })
        if r.status_code == 401:
            self._token = None
        r.raise_for_status()
        return r.json() or []

    # --- Polling ---

    def poll_once(self):
        try:
            token = self._get_token()
        except (requests.RequestException, KeyError, ValueError) as e:
            log.error("RAPT authentication failed: %s", e)
            return

        count = 0
        for endpoint, model in ENDPOINTS.items():
            try:
                devices = self._get(endpoint, token)
            except (requests.RequestException, ValueError) as e:
                log.warning("%s failed: %s", endpoint, e)
                continue
            for device in devices:
                if not device.get("id") or device.get("deleted"):
                    continue
                self._publish_device(device, model)
                count += 1
        log.info("Published %d device(s).", count)

    def _build_state(self, device):
        state = {k: device[k] for k in STATE_FIELDS if k in device}

        # The API reports gravity as SG x 1000 (e.g. 1048.2); normalise to 1.0482.
        gravity = state.get("gravity")
        if isinstance(gravity, (int, float)):
            state["specific_gravity"] = round(gravity / 1000 if gravity > 2 else gravity, 4)

        # coolingEnabled/heatingEnabled don't track the relays, so infer activity
        # from the runtime counters advancing between polls (as upstream does).
        if "coolingRunTime" in state or "heatingRunTime" in state:
            current = (state.get("coolingRunTime") or 0, state.get("heatingRunTime") or 0)
            previous = self._runtimes.get(state["id"])
            state["cooling_active"] = previous is not None and current[0] > previous[0]
            state["heating_active"] = previous is not None and current[1] > previous[1]
            self._runtimes[state["id"]] = current

        return state

    def _publish_device(self, device, model):
        state = self._build_state(device)
        device_id = state["id"]
        state_topic = f"{self._cfg['base_topic']}/{device_id}/state"

        self._publish_discovery(state, model, state_topic)
        self._client.publish(state_topic, json.dumps(state), qos=0, retain=True)
        log.debug("%s -> %s", state.get("name"), state_topic)

    def _publish_discovery(self, state, model, state_topic):
        device_id = state["id"]
        node_id = f"rapt_{sanitize(device_id)}"
        device_block = {
            "identifiers": [node_id],
            "name": state.get("name") or model,
            "manufacturer": "KegLand",
            "model": model,
        }
        if state.get("firmwareVersion"):
            device_block["sw_version"] = state["firmwareVersion"]

        for entity in ENTITIES:
            key = entity["key"]
            if state.get(key) is None or (device_id, key) in self._announced:
                continue

            if "template" in entity:
                template = entity["template"]
            elif entity["component"] == "binary_sensor":
                template = "{{ 'ON' if value_json." + key + " else 'OFF' }}"
            else:
                template = "{{ value_json." + key + " }}"

            payload = {
                "name": entity["name"],
                "unique_id": f"{node_id}_{sanitize(key)}",
                "state_topic": state_topic,
                "value_template": template,
                "availability_topic": self.status_topic,
                # Go unavailable rather than show stale data if the API stops answering
                "expire_after": self._cfg["poll_interval"] * 3,
                "device": device_block,
                **entity["config"],
            }
            topic = (f"{self._cfg['discovery_prefix']}/{entity['component']}/"
                     f"{node_id}/{sanitize(key)}/config")
            self._client.publish(topic, json.dumps(payload), qos=0, retain=True)
            self._announced.add((device_id, key))


def load_config():
    missing = [k for k in ("RAPT_EMAIL", "RAPT_SECRET", "MQTT_HOST") if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing required environment variable(s): {', '.join(missing)}")
    return {
        "rapt_email": os.environ["RAPT_EMAIL"],
        "rapt_secret": os.environ["RAPT_SECRET"],
        "mqtt_host": os.environ["MQTT_HOST"],
        "mqtt_port": int(os.environ.get("MQTT_PORT", 1883)),
        "mqtt_username": os.environ.get("MQTT_USERNAME", ""),
        "mqtt_password": os.environ.get("MQTT_PASSWORD", ""),
        "mqtt_tls": os.environ.get("MQTT_TLS", "").lower() in ("true", "1", "yes"),
        # RAPT tracks API usage and can revoke access for abuse; don't go below 60s
        "poll_interval": max(60, int(os.environ.get("POLL_INTERVAL", 300))),
        "base_topic": os.environ.get("BASE_TOPIC", "rapt2mqtt").strip("/"),
        "discovery_prefix": os.environ.get("HA_DISCOVERY_PREFIX", "homeassistant").strip("/"),
    }


def main():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = load_config()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rapt2mqtt")
    bridge = Bridge(cfg, client)
    connected = threading.Event()
    stop = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("MQTT connection refused: %s", reason_code)
            return
        log.info("Connected to MQTT broker.")
        bridge.reset_discovery()
        client.publish(bridge.status_topic, "online", qos=1, retain=True)
        connected.set()

    def on_disconnect(client, userdata, flags, reason_code, properties):
        connected.clear()
        if not stop.is_set():
            log.warning("MQTT disconnected (%s). Will auto-reconnect.", reason_code)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    if cfg["mqtt_username"]:
        client.username_pw_set(cfg["mqtt_username"], cfg["mqtt_password"])
    if cfg["mqtt_tls"]:
        client.tls_set()
    client.will_set(bridge.status_topic, "offline", qos=1, retain=True)
    client.reconnect_delay_set(min_delay=1, max_delay=120)

    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    log.info("Connecting to MQTT broker at %s:%s...", cfg["mqtt_host"], cfg["mqtt_port"])
    client.connect_async(cfg["mqtt_host"], cfg["mqtt_port"], keepalive=60)
    client.loop_start()

    while not stop.is_set():
        if connected.wait(timeout=10):
            try:
                bridge.poll_once()
            except Exception:
                log.exception("Unexpected error in poll loop")
            stop.wait(timeout=cfg["poll_interval"])
        else:
            log.warning("Waiting for MQTT broker...")

    log.info("Shutting down.")
    if connected.is_set():
        client.publish(bridge.status_topic, "offline", qos=1, retain=True).wait_for_publish(5)
    client.disconnect()
    client.loop_stop()


if __name__ == "__main__":
    main()
