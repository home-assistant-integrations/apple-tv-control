"""Coordinator for the Apple TV Control integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

import pyatv
from pyatv.const import Protocol
from pyatv.exceptions import PyatvError
from pyatv.interface import AppleTV, BaseConfig, Playing, PowerState, PushUpdater

from .const import (
    CONF_COMPANION_CREDENTIALS,
    CONF_HOST,
    CONF_MRP_CREDENTIALS,
    CONF_NAME,
    DOMAIN,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_DELAY,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

MRP_PROTOCOL = Protocol.MRP
COMPANION_PROTOCOL = Protocol.Companion


@dataclass
class AppleTvData:
    """Data held by the coordinator."""

    power_state: PowerState = PowerState.Unknown
    playing: Playing | None = None
    connected: bool = False
    app_name: str | None = None


class AppleTvCoordinator(DataUpdateCoordinator[AppleTvData]):
    """Manages Apple TV connection and state updates."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.config_entry = config_entry
        self.atv: AppleTV | None = None
        self._push_updater: PushUpdater | None = None
        self._connected = False
        self._reconnect_attempts = 0

        # Connection parameters from config entry
        self._host = config_entry.data[CONF_HOST]
        self._identifier = config_entry.data[CONF_IDENTIFIER]
        self._mrp_credentials = config_entry.data.get(CONF_MRP_CREDENTIALS)
        self._companion_credentials = config_entry.data.get(CONF_COMPANION_CREDENTIALS)
        self._name = config_entry.data.get(CONF_NAME, DOMAIN)

        # Initialize data
        self.data = AppleTvData()

    @property
    def connected(self) -> bool:
        """Return whether the coordinator is connected to the device."""
        return self._connected

    async def _async_setup_services(self, config: BaseConfig) -> None:
        """Apply credentials to the config services."""
        if self._mrp_credentials:
            mrp_service = config.get_service(MRP_PROTOCOL)
            if mrp_service:
                mrp_service.credentials = self._mrp_credentials

        if self._companion_credentials:
            companion_service = config.get_service(COMPANION_PROTOCOL)
            if companion_service:
                companion_service.credentials = self._companion_credentials

    async def connect(self) -> None:
        """Establish connection to the Apple TV."""
        if self._connected:
            return

        _LOGGER.info("Connecting to Apple TV at %s", self._host)

        try:
            loop = self.hass.loop
            # Scan for the specific device
            devices = await pyatv.scan(loop, hosts=[self._host])
            if not devices:
                raise ConfigEntryNotReady(
                    f"Apple TV at {self._host} not found on the network"
                )

            config = devices[0]
            await self._async_setup_services(config)

            # Connect to the device
            self.atv = await pyatv.connect(config, loop)
            self._connected = True
            self._reconnect_attempts = 0

            # Set up push updater for real-time state changes
            self._push_updater = self.atv.push_updater
            self._push_updater.listener = self
            await self._push_updater.start()

            # Fetch initial state
            await self._fetch_state()

            _LOGGER.info("Connected to Apple TV %s", self._name)

        except ConfigEntryNotReady:
            raise
        except PyatvError as ex:
            raise ConfigEntryNotReady(
                f"Failed to connect to Apple TV at {self._host}: {ex}"
            ) from ex

    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        if not self._connected:
            return

        _LOGGER.info("Disconnecting from Apple TV %s", self._name)

        # Stop push updater first
        if self._push_updater:
            try:
                await self._push_updater.stop()
            except PyatvError as ex:
                _LOGGER.debug("Error stopping push updater: %s", ex)
            self._push_updater = None

        # Close the connection
        if self.atv:
            try:
                self.atv.close()
            except PyatvError as ex:
                _LOGGER.debug("Error closing connection: %s", ex)
            self.atv = None

        self._connected = False
        self.data = AppleTvData()

    async def _async_update_data(self) -> AppleTvData:
        """Poll power state and metadata from the device.

        This is called by the coordinator's polling interval as a fallback
        when push updates are not available.
        """
        if not self._connected or not self.atv:
            return AppleTvData()

        try:
            await self._fetch_state()
        except PyatvError as ex:
            _LOGGER.warning("Polling failed: %s", ex)
            raise UpdateFailed(str(ex)) from ex

        return self.data

    async def _fetch_state(self) -> None:
        """Fetch current power state and metadata from the device."""
        if not self.atv:
            return

        # Fetch power state
        try:
            power = self.atv.power
            self.data.power_state = power.power_state
        except PyatvError as ex:
            _LOGGER.debug("Failed to fetch power state: %s", ex)

        # Fetch metadata (playing info)
        try:
            metadata = self.atv.metadata
            playing = await metadata.playing()
            self.data.playing = playing
            if playing and playing.title:
                self.data.app_name = playing.title
        except PyatvError as ex:
            _LOGGER.debug("Failed to fetch metadata: %s", ex)
            self.data.playing = None

        self.data.connected = self._connected

    async def _handle_reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            _LOGGER.warning(
                "Max reconnection attempts (%d) reached for %s",
                MAX_RECONNECT_ATTEMPTS,
                self._name,
            )
            self.data.connected = False
            self.async_set_updated_data(self.data)
            return

        self._reconnect_attempts += 1
        delay = RECONNECT_DELAY * (2 ** (self._reconnect_attempts - 1))
        _LOGGER.info(
            "Reconnecting to %s in %d seconds (attempt %d/%d)",
            self._name,
            delay,
            self._reconnect_attempts,
            MAX_RECONNECT_ATTEMPTS,
        )

        try:
            await self.disconnect()
            await self.hass.async_create_task(self.connect())
        except (ConfigEntryNotReady, PyatvError) as ex:
            _LOGGER.warning("Reconnection attempt %d failed: %s", self._reconnect_attempts, ex)

    # PushUpdater listener methods

    async def push_update(self, updater: PushUpdater, data: Playing) -> None:
        """Handle push update from the device."""
        _LOGGER.debug("Received push update: %s", data)
        self.data.playing = data
        if data and data.title:
            self.data.app_name = data.title
        self.data.connected = self._connected
        self.async_set_updated_data(self.data)

    async def connection_lost(self) -> None:
        """Handle connection lost event from push updater."""
        _LOGGER.warning("Connection lost to %s, attempting to reconnect", self._name)
        self._connected = False
        await self._handle_reconnect()

    @property
    def remote_control(self) -> pyatv.interface.RemoteControl:
        """Return the remote control interface."""
        if not self.atv:
            raise RuntimeError("Not connected to Apple TV")
        return self.atv.remote_control

    @property
    def power(self) -> pyatv.interface.Power:
        """Return the power management interface."""
        if not self.atv:
            raise RuntimeError("Not connected to Apple TV")
        return self.atv.power

    @property
    def metadata(self) -> pyatv.interface.Metadata:
        """Return the metadata interface."""
        if not self.atv:
            raise RuntimeError("Not connected to Apple TV")
        return self.atv.metadata


async def async_setup_coordinator(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> AppleTvCoordinator:
    """Set up the coordinator for a config entry."""
    coordinator = AppleTvCoordinator(hass, config_entry)
    try:
        await coordinator.connect()
    except ConfigEntryNotReady:
        raise
    except Exception as ex:
        raise ConfigEntryNotReady(
            f"Failed to set up coordinator for {config_entry.data.get(CONF_NAME, 'Apple TV')}: {ex}"
        ) from ex
    return coordinator
