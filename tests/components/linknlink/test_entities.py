"""Tests for LinknLink entities."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiolinknlink import UltraConnectionError

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import STATE

from tests.common import MockConfigEntry


async def test_entities(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test gateway and child-device entities."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.emotion_ultra2_temperature").state == "23.5"
    assert hass.states.get("sensor.emotion_ultra2_target_count").state == "1"
    assert hass.states.get("sensor.emotion_ultra2_zone_2_target_count").state == "1"
    assert hass.states.get("binary_sensor.emotion_ultra2_occupancy").state == STATE_ON
    assert (
        hass.states.get("binary_sensor.emotion_ultra2_zone_1_occupancy").state
        == STATE_OFF
    )
    assert hass.states.get("sensor.radar_temperature").state == "24.0"
    assert hass.states.get("binary_sensor.radar_occupancy").state == STATE_ON

    assert hass.states.get("sensor.emotion_ultra2_wi_fi_signal_strength") is None
    registry_entry = er.async_get(hass).async_get(
        "sensor.emotion_ultra2_wi_fi_signal_strength"
    )
    assert registry_entry is not None
    assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_entities_unavailable_when_device_reports_offline(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities are unavailable when the protocol reports offline."""
    mock_linknlink_client.refresh.return_value = replace(STATE, online=False)

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.emotion_ultra2_temperature").state == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("binary_sensor.emotion_ultra2_occupancy").state
        == STATE_UNAVAILABLE
    )


async def test_entities_recover_after_update_failure(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities become unavailable on an update error and recover."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    mock_linknlink_client.refresh.side_effect = UltraConnectionError("offline")

    await coordinator.async_refresh()

    assert (
        hass.states.get("sensor.emotion_ultra2_temperature").state == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("binary_sensor.emotion_ultra2_occupancy").state
        == STATE_UNAVAILABLE
    )

    mock_linknlink_client.refresh.side_effect = None
    mock_linknlink_client.refresh.return_value = STATE
    await coordinator.async_refresh()

    assert hass.states.get("sensor.emotion_ultra2_temperature").state == "23.5"
    assert hass.states.get("binary_sensor.emotion_ultra2_occupancy").state == STATE_ON


async def test_unsupported_sensor_is_not_created(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors absent from the first refresh are not created."""
    mock_linknlink_client.refresh.return_value = replace(
        STATE, values={"envtemp": 23.5}, children={}
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.emotion_ultra2_temperature") is not None
    assert hass.states.get("sensor.emotion_ultra2_humidity") is None
    assert hass.states.get("binary_sensor.emotion_ultra2_occupancy") is None
