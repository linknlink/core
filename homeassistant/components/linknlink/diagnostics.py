"""Diagnostics support for LinknLink."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .coordinator import LinknLinkConfigEntry

TO_REDACT = {
    CONF_HOST,
    CONF_MAC,
    CONF_UNIQUE_ID,
    "URL",
    "account",
    "connected_ssid",
    "detect_position",
    "dev_ip",
    "device_id",
    "did",
    "id",
    "ip",
    "mac",
    "mqtt_broker",
    "mqtt_password",
    "mqtt_username",
    "password",
    "ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LinknLinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a LinknLink config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "config_entry": entry.as_dict(),
            "device": asdict(coordinator.device),
            "state": asdict(coordinator.data),
            "last_update_success": coordinator.last_update_success,
        },
        TO_REDACT,
    )
