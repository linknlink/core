"""Distance sensors for LinknLink eMotion Ultra2 target positions."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LinknLinkConfigEntry
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0

POSITION_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="nearest_horizontal_distance",
        translation_key="nearest_horizontal_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="nearest_distance",
        translation_key="nearest_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ultra2 position distance sensors."""
    async_add_entities(
        LinknLinkPositionSensor(entry.runtime_data, description)
        for description in POSITION_SENSOR_DESCRIPTIONS
    )


class LinknLinkPositionSensor(LinknLinkEntity, SensorEntity):
    """Representation of an Ultra2 nearest-target distance."""

    entity_description: SensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether a fresh target position is available."""
        state = self.coordinator.position_state
        return (
            state is not None
            and state.subscribed
            and not state.stale
            and state.latest_update is not None
            and self.native_value is not None
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the nearest target distance in meters."""
        state = self.coordinator.position_state
        if state is None or state.latest_update is None:
            return None
        if self.entity_description.key == "nearest_horizontal_distance":
            return state.latest_update.nearest_horizontal_distance
        return state.latest_update.nearest_distance

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to high-frequency position updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_position_listener(
                self._async_handle_position_update
            )
        )

    @callback
    def _async_handle_position_update(self, _: object) -> None:
        """Write a new distance or expiry state."""
        self.async_write_ha_state()
