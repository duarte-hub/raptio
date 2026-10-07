"""Data update coordinator for the RAPT integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RaptApiError, RaptAuthError, RaptClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type RaptioConfigEntry = ConfigEntry[RaptioCoordinator]


class RaptioCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls every RAPT device on the account."""

    config_entry: RaptioConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RaptioConfigEntry, client: RaptClient) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self._runtimes: dict[str, tuple[float, float]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.client.async_get_devices()
        except RaptAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RaptApiError as err:
            raise UpdateFailed(str(err)) from err

        for device_id, device in devices.items():
            # The API may report gravity as SG x 1000 (e.g. 1048.2); normalise to 1.0482.
            gravity = device.get("gravity")
            if isinstance(gravity, (int, float)):
                device["specific_gravity"] = round(
                    gravity / 1000 if gravity > 2 else gravity, 4
                )

            # Infer relay activity from the runtime counters advancing between polls.
            if "coolingRunTime" in device or "heatingRunTime" in device:
                current = (device.get("coolingRunTime") or 0, device.get("heatingRunTime") or 0)
                previous = self._runtimes.get(device_id)
                device["cooling_active"] = previous is not None and current[0] > previous[0]
                device["heating_active"] = previous is not None and current[1] > previous[1]
                self._runtimes[device_id] = current

        return devices
