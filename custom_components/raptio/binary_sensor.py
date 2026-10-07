"""Binary sensors for the RAPT integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RaptioConfigEntry
from .entity import RaptioEntity, async_setup_raptio_entities


@dataclass(frozen=True, kw_only=True)
class RaptioBinarySensorDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[Any], bool] = bool


# key is the field name in the coordinator's device record
BINARY_SENSORS = (
    RaptioBinarySensorDescription(
        key="cooling_active",
        translation_key="cooling",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    RaptioBinarySensorDescription(
        key="heating_active",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    RaptioBinarySensorDescription(
        key="connectionState",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda value: value == "Connected",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RaptioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_setup_raptio_entities(entry, async_add_entities, BINARY_SENSORS, RaptioBinarySensor)


class RaptioBinarySensor(RaptioEntity, BinarySensorEntity):
    """An on/off state of a RAPT device."""

    entity_description: RaptioBinarySensorDescription

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self._value)
