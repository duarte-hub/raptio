"""Constants for the RAPT integration."""

import logging

DOMAIN = "raptio"
LOGGER = logging.getLogger(__package__)

CONF_API_SECRET = "api_secret"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 300
# RAPT tracks API usage and can revoke access for abuse; don't go below 60s
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 3600

TOKEN_URL = "https://id.rapt.io/connect/token"
API_URL = "https://api.rapt.io/api/"

# List endpoint -> model name shown in the device registry
ENDPOINTS = {
    "TemperatureControllers/GetTemperatureControllers": "RAPT Temperature Controller",
    "Hydrometers/GetHydrometers": "RAPT Pill Hydrometer",
    "FermentationChambers/GetFermentationChambers": "RAPT Fermentation Chamber",
    "BrewZillas/GetBrewZillas": "BrewZilla",
    "Stills/GetStills": "RAPT Still",
    "BondedDevices/GetBondedDevices": "RAPT Bonded Device",
}

# API fields kept from each device record
STATE_FIELDS = (
    "id", "name", "temperature", "targetTemperature", "gravity", "gravityVelocity",
    "battery", "rssi", "connectionState", "firmwareVersion",
    "coolingRunTime", "heatingRunTime",
)
