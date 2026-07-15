"""Tests for LinknLink setup."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

from aiolinknlink import UltraConnectionError, UltraError
import pytest

from homeassistant.components.linknlink.const import DISPLAY_MODEL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import DEVICE, MAC, SESSION

from tests.common import MockConfigEntry


async def test_setup_updates_previous_display_name(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating an entry created with the previous display name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="eMotion Ultra2",
        data=mock_config_entry.data,
        unique_id=mock_config_entry.unique_id,
    )

    await setup_integration(hass, entry)

    assert entry.title == DISPLAY_MODEL


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test setting up and unloading an entry."""
    mock_linknlink_client.connect.return_value = replace(
        SESSION, device=replace(DEVICE, model=DISPLAY_MODEL)
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_linknlink_client.connect.assert_awaited_once()
    subscription_class, subscription = mock_position_subscription
    subscription_class.assert_called_once()
    subscription.start.assert_awaited_once()
    subscription.wait_confirmed.assert_awaited_once_with(60.0)
    subscription.get_radar_status.assert_awaited_once()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MAC)})
    assert device is not None
    assert device.model == DISPLAY_MODEL

    coordinator = mock_config_entry.runtime_data
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    subscription.stop.assert_awaited_once()
    with pytest.raises(UltraError, match="not available"):
        await coordinator.async_set_radar_sensitivity(1)


async def test_setup_continues_when_radar_configuration_is_unavailable(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test position setup when the optional radar status read fails."""
    _, subscription = mock_position_subscription
    subscription.get_radar_status.side_effect = UltraConnectionError("offline")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.radar_status is None


async def test_setup_retries_when_device_is_unavailable(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when the device cannot be reached."""
    mock_linknlink_client.connect.side_effect = UltraConnectionError("offline")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_subscription_is_not_confirmed(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test setup retry and socket cleanup after confirmation times out."""
    _, subscription = mock_position_subscription
    subscription.wait_confirmed.side_effect = TimeoutError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    subscription.stop.assert_awaited_once()


async def test_setup_retries_when_position_listener_fails(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_position_subscription: tuple[MagicMock, MagicMock],
) -> None:
    """Test setup retry when the local UDP listener cannot start."""
    _, subscription = mock_position_subscription
    subscription.start.side_effect = OSError("cannot bind")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    subscription.stop.assert_awaited_once()
