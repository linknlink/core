"""Tests for the LinknLink target-position event entity."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MAC, POSITION_STATE, POSITION_UPDATE

from tests.common import MockConfigEntry


def _position_entity_ids(hass: HomeAssistant) -> tuple[str, str, str]:
    """Return the two distance sensor IDs and target-position event ID."""
    registry = er.async_get(hass)
    horizontal_id = registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_nearest_horizontal_distance"
    )
    distance_id = registry.async_get_entity_id(
        "sensor", "linknlink", f"{MAC}_nearest_distance"
    )
    event_id = registry.async_get_entity_id(
        "event", "linknlink", f"{MAC}_target_position"
    )
    assert horizontal_id is not None
    assert distance_id is not None
    assert event_id is not None
    return horizontal_id, distance_id, event_id


async def test_event_entity_setup(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the two distance sensors and target-position event entity."""
    await setup_integration(hass, mock_config_entry)

    horizontal_id, distance_id, event_id = _position_entity_ids(hass)
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"
    assert hass.states.get(event_id) is not None
    assert {
        entry.unique_id
        for entry in er.async_get(hass).entities.get_entries_for_config_entry_id(
            mock_config_entry.entry_id
        )
    } == {
        f"{MAC}_nearest_distance",
        f"{MAC}_nearest_horizontal_distance",
        f"{MAC}_target_position",
    }


async def test_position_event_and_availability(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test typed position events and subscription availability."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_position_subscription
    position_callback = subscription_class.call_args.kwargs["callback"]
    status_callback = subscription_class.call_args.kwargs["status_callback"]
    horizontal_id, distance_id, event_id = _position_entity_ids(hass)

    subscription.state = POSITION_STATE
    position_callback(POSITION_UPDATE)
    await hass.async_block_till_done()

    event_state = hass.states.get(event_id)
    assert event_state is not None
    assert event_state.attributes["event_type"] == "position_update"
    assert event_state.attributes["target_count"] == 1
    assert event_state.attributes["targets"] == [{"x": 0.3, "y": 0.4, "z": 1.2}]
    assert event_state.attributes["nearest_horizontal_distance"] == 0.5
    assert event_state.attributes["nearest_distance"] == 1.3
    assert hass.states.get(horizontal_id).state == "0.5"
    assert hass.states.get(distance_id).state == "1.3"

    status_callback(replace(POSITION_STATE, stale=True))
    await hass.async_block_till_done()
    assert hass.states.get(horizontal_id).state == STATE_UNAVAILABLE
    assert hass.states.get(distance_id).state == STATE_UNAVAILABLE

    status_callback(replace(POSITION_STATE, subscribed=False, last_error="offline"))
    await hass.async_block_till_done()
    assert hass.states.get(event_id).state == STATE_UNAVAILABLE
    assert hass.states.get(horizontal_id).state == STATE_UNAVAILABLE
    assert hass.states.get(distance_id).state == STATE_UNAVAILABLE

    status_callback(POSITION_STATE)
    await hass.async_block_till_done()
    assert hass.states.get(event_id).state != STATE_UNAVAILABLE


async def test_empty_position_event(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test a position update reporting no targets."""
    await setup_integration(hass, mock_config_entry)
    subscription_class, subscription = mock_position_subscription
    position_callback = subscription_class.call_args.kwargs["callback"]
    horizontal_id, distance_id, event_id = _position_entity_ids(hass)
    empty_update = replace(POSITION_UPDATE, targets=())
    subscription.state = replace(POSITION_STATE, latest_update=empty_update)

    position_callback(empty_update)
    await hass.async_block_till_done()

    event_state = hass.states.get(event_id)
    assert event_state is not None
    assert event_state.attributes["target_count"] == 0
    assert event_state.attributes["targets"] == []
    assert event_state.attributes["nearest_horizontal_distance"] is None
    assert event_state.attributes["nearest_distance"] is None
    assert hass.states.get(horizontal_id).state == STATE_UNAVAILABLE
    assert hass.states.get(distance_id).state == STATE_UNAVAILABLE
