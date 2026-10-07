"""Sensors for the RAPT integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import RaptioConfigEntry
from .entity import RaptioEntity, async_setup_raptio_entities

# key is the field name in the coordinator's device record
SENSORS = (
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="targetTemperature",
        translation_key="target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="specific_gravity",
        translation_key="gravity",
        native_unit_of_measurement="SG",
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="gravityVelocity",
        translation_key="gravity_velocity",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RaptioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_setup_raptio_entities(entry, async_add_entities, SENSORS, RaptioSensor)


class RaptioSensor(RaptioEntity, SensorEntity):
    """A numeric reading from a RAPT device."""

    @property
    def native_value(self) -> StateType:
        return self._value
