"""Coordinator for LinknLink eMotion Ultra2 local position updates."""

from collections.abc import Callable
from typing import override

from aiolinknlink import (
    UltraClient,
    UltraDevice,
    UltraError,
    UltraPositionSubscription,
    UltraPositionSubscriptionState,
    UltraPositionUpdate,
    UltraRadarStatus,
    UltraSession,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, POSITION_SUBSCRIPTION_CONFIRM_TIMEOUT

type LinknLinkConfigEntry = ConfigEntry[LinknLinkCoordinator]
type PositionListener = Callable[[UltraPositionUpdate | None], None]
type ConfigListener = Callable[[], None]


class LinknLinkCoordinator(DataUpdateCoordinator[None]):
    """Manage one Ultra2 DNA session and local position subscription."""

    config_entry: LinknLinkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LinknLinkConfigEntry,
        client: UltraClient,
        device: UltraDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=f"LinknLink {device.id}",
        )
        self.client = client
        self.device = device
        self.session: UltraSession | None = None
        self.position_subscription: UltraPositionSubscription | None = None
        self.position_state: UltraPositionSubscriptionState | None = None
        self.radar_status: UltraRadarStatus | None = None
        self._position_listeners: set[PositionListener] = set()
        self._config_listeners: set[ConfigListener] = set()
        self._setup_complete = False

    @override
    async def _async_setup(self) -> None:
        """Authenticate and start the local UDP position subscription."""
        try:
            self.session = await self.client.connect(self.device)
            self.position_subscription = UltraPositionSubscription(
                self.client,
                self.session,
                callback=self._async_handle_position,
                status_callback=self._async_handle_position_status,
            )
            await self.position_subscription.start()
            await self.position_subscription.wait_confirmed(
                POSITION_SUBSCRIPTION_CONFIRM_TIMEOUT
            )
            self.position_state = self.position_subscription.state
            try:
                self.radar_status = await self.position_subscription.get_radar_status()
            except UltraError as err:
                LOGGER.warning("Unable to read Ultra2 radar configuration: %s", err)
            self._setup_complete = True
        except (OSError, TimeoutError, UltraError, ValueError) as err:
            if self.position_subscription is not None:
                await self.position_subscription.stop()
                self.position_subscription = None
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err

    @override
    async def _async_update_data(self) -> None:
        """Complete the coordinator's one-time initial refresh."""

    @callback
    def async_add_position_listener(
        self, listener: PositionListener
    ) -> Callable[[], None]:
        """Register a callback for position or position-status changes."""
        self._position_listeners.add(listener)

        @callback
        def _remove_listener() -> None:
            self._position_listeners.discard(listener)

        return _remove_listener

    @callback
    def async_add_config_listener(self, listener: ConfigListener) -> Callable[[], None]:
        """Register a callback for radar configuration changes."""
        self._config_listeners.add(listener)

        @callback
        def _remove_listener() -> None:
            self._config_listeners.discard(listener)

        return _remove_listener

    async def async_set_radar_sensitivity(self, sensitivity: int) -> None:
        """Set radar sensitivity and store the device-confirmed value."""
        if self.position_subscription is None:
            raise UltraError("position subscription is not available")
        self.radar_status = await self.position_subscription.set_radar_sensitivity(
            sensitivity
        )
        self._async_notify_config_listeners()

    async def async_set_radar_trigger_speed(self, trigger_speed: int) -> None:
        """Set radar trigger speed and store the device-confirmed value."""
        subscription = self._radar_subscription()
        self.radar_status = await subscription.set_radar_trigger_speed(trigger_speed)
        self._async_notify_config_listeners()

    async def async_set_radar_install_mode(self, install_mode: int) -> None:
        """Set installation mode and store the device-confirmed value."""
        subscription = self._radar_subscription()
        self.radar_status = await subscription.set_radar_install_mode(install_mode)
        self._async_notify_config_listeners()

    async def async_set_radar_install_direction(self, install_direction: int) -> None:
        """Set cable orientation and store the device-confirmed value."""
        subscription = self._radar_subscription()
        self.radar_status = await subscription.set_radar_install_direction(
            install_direction
        )
        self._async_notify_config_listeners()

    def _radar_subscription(self) -> UltraPositionSubscription:
        """Return the running subscription used for serialized radar operations."""
        if self.position_subscription is None:
            raise UltraError("position subscription is not available")
        return self.position_subscription

    @callback
    def _async_handle_position(self, update: UltraPositionUpdate) -> None:
        """Forward a new target-position update to position entities."""
        assert self.position_subscription is not None
        self.position_state = self.position_subscription.state
        for listener in self._position_listeners:
            listener(update)

    @callback
    def _async_handle_position_status(
        self, state: UltraPositionSubscriptionState
    ) -> None:
        """Forward meaningful subscription or expiry state changes."""
        previous = self.position_state
        self.position_state = state
        if previous is not None and (
            previous.subscribed,
            previous.stale,
            previous.last_error,
        ) == (state.subscribed, state.stale, state.last_error):
            return
        if state.last_error and (previous is None or previous.subscribed):
            LOGGER.warning(
                "Ultra2 local position subscription is unavailable: %s",
                state.last_error,
            )
        elif state.subscribed and previous is not None and not previous.subscribed:
            LOGGER.info("Ultra2 local position subscription is available")
            if self._setup_complete:
                self.config_entry.async_create_background_task(
                    self.hass,
                    self._async_refresh_radar_status(),
                    "Refresh LinknLink radar configuration",
                )
        if previous is not None and previous.subscribed and not state.subscribed:
            self.radar_status = None
            self._async_notify_config_listeners()
        for listener in self._position_listeners:
            listener(None)

    async def _async_refresh_radar_status(self) -> None:
        """Refresh radar configuration after a recovered subscription."""
        if self.position_subscription is None:
            return
        try:
            self.radar_status = await self.position_subscription.get_radar_status()
        except UltraError as err:
            LOGGER.warning("Unable to refresh Ultra2 radar configuration: %s", err)
            return
        self._async_notify_config_listeners()

    @callback
    def _async_notify_config_listeners(self) -> None:
        """Notify radar configuration entities."""
        for listener in self._config_listeners:
            listener()

    @override
    async def async_shutdown(self) -> None:
        """Stop the local position subscription and release its socket."""
        if self.position_subscription is not None:
            await self.position_subscription.stop()
            self.position_subscription = None
        await super().async_shutdown()
