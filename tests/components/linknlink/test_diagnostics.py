"""Tests for LinknLink diagnostics."""

from unittest.mock import AsyncMock

from homeassistant.components.linknlink.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_diagnostics_are_redacted(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that diagnostics do not expose device identifiers or private data."""
    await setup_integration(hass, mock_config_entry)

    result = await async_get_config_entry_diagnostics(
        hass,
        mock_config_entry,  # type: ignore[arg-type]
    )

    assert result["config_entry"]["data"]["host"] == "**REDACTED**"
    assert result["config_entry"]["data"]["mac"] == "**REDACTED**"
    assert result["config_entry"]["unique_id"] == "**REDACTED**"
    assert result["device"]["ip"] == "**REDACTED**"
    assert result["device"]["mac"] == "**REDACTED**"
    assert result["state"]["values"]["detect_position"] == "**REDACTED**"
