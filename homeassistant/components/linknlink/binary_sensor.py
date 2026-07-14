"""Binary sensor platform for LinknLink."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LinknLinkConfigEntry, LinknLinkCoordinator
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="presence",
        translation_key="occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="zone_1_presence",
        translation_key="zone_1_occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="zone_2_presence",
        translation_key="zone_2_occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="zone_3_presence",
        translation_key="zone_3_occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="zone_4_presence",
        translation_key="zone_4_occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LinknLink binary sensors."""
    coordinator = entry.runtime_data
    entities: list[LinknLinkBinarySensor] = [
        LinknLinkBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.key in coordinator.data.values
    ]
    entities.extend(
        LinknLinkBinarySensor(coordinator, description, subdevice_id)
        for subdevice_id, child in coordinator.data.children.items()
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.key in child.fields
    )
    async_add_entities(entities)


class LinknLinkBinarySensor(LinknLinkEntity, BinarySensorEntity):
    """Representation of a LinknLink binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: BinarySensorEntityDescription,
        subdevice_id: str | None = None,
    ) -> None:
        """Initialize a LinknLink binary sensor."""
        super().__init__(coordinator, description, subdevice_id)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether presence is detected."""
        value = self.source_value
        return None if value is None else bool(value)
