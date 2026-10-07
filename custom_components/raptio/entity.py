"""Base entity for the RAPT integration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RaptioConfigEntry, RaptioCoordinator


class RaptioEntity(CoordinatorEntity[RaptioCoordinator]):
    """One value of one RAPT device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: RaptioCoordinator, device_id: str, description: EntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        device = coordinator.data[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("name") or device["model"],
            manufacturer="KegLand",
            model=device["model"],
            sw_version=device.get("firmwareVersion"),
        )

    @property
    def available(self) -> bool:
        return super().available and self._device_id in self.coordinator.data

    @property
    def _value(self) -> Any:
        return self.coordinator.data[self._device_id].get(self.entity_description.key)


@callback
def async_setup_raptio_entities(
    entry: RaptioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    descriptions: Sequence[EntityDescription],
    entity_factory: Callable[[RaptioCoordinator, str, Any], RaptioEntity],
) -> None:
    """Add an entity for each value a device reports, including devices that show up later."""
    coordinator = entry.runtime_data
    known: set[tuple[str, str]] = set()

    @callback
    def _async_add_new() -> None:
        new = []
        for device_id, device in coordinator.data.items():
            for description in descriptions:
                if (device_id, description.key) in known or device.get(description.key) is None:
                    continue
                known.add((device_id, description.key))
                new.append(entity_factory(coordinator, device_id, description))
        if new:
            async_add_entities(new)

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
