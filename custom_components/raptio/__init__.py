"""RAPT cloud integration: polls the KegLand RAPT API for brewing devices."""

from __future__ import annotations

from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RaptClient
from .const import CONF_API_SECRET
from .coordinator import RaptioConfigEntry, RaptioCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RaptioConfigEntry) -> bool:
    client = RaptClient(
        async_get_clientsession(hass), entry.data[CONF_EMAIL], entry.data[CONF_API_SECRET]
    )
    coordinator = RaptioCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RaptioConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: RaptioConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
