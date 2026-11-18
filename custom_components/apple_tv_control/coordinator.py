"""Connection and state handling for the Apple TV Control integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

import pyatv
from pyatv import exceptions
from pyatv.const import FeatureName, FeatureState, PowerState, Protocol
from pyatv.interface import AppleTV, BaseConfig, OutputDevice, Playing, PushUpdater

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CREDENTIALS,
    CONF_HOST,
    MAX_RECONNECT_ATTEMPTS,
    PYATV_ERRORS,
    RECONNECT_DELAY,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# pyatv errors meaning the stored pairing credentials are no longer accepted
AUTH_ERRORS = (
    exceptions.AuthenticationError,
    exceptions.InvalidCredentialsError,
    exceptions.NoCredentialsError,
)

type AppleTvConfigEntry = ConfigEntry[AppleTvCoordinator]


class CannotConnect(Exception):
    """The Apple TV could not be reached."""


async def async_scan_host(hass: HomeAssistant, host: str) -> BaseConfig | None:
    """Scan one host and return its pyatv configuration, or None if nothing answered.

    Uses Home Assistant's zeroconf instance. Without it pyatv knocks on the
    device's ports first and, when the host is unreachable (Apple TV off),
    leaves the failed knocks behind as "Task exception was never retrieved"
    errors in the log.
    """
    aiozc = await zeroconf.async_get_async_instance(hass)
    devices = await pyatv.scan(hass.loop, hosts=[host], aiozc=aiozc)
    return devices[0] if devices else None


@dataclass
class AppleTvData:
    """State of the Apple TV."""

    power_state: PowerState = PowerState.Unknown
    playing: Playing | None = None
    app_name: str | None = None
    position_updated_at: datetime | None = None
    volume: float | None = None  # percent, only meaningful when can_set_volume


class AppleTvCoordinator(DataUpdateCoordinator[AppleTvData]):
    """Keeps the connection to one Apple TV and its state.

    State changes are pushed by pyatv through the listener methods below; the
    polling interval is a fallback that also reconnects a lost connection.
    """

    config_entry: AppleTvConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: AppleTvConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.atv: AppleTV | None = None
        self.data = AppleTvData()
        self._closing = False
        self._reconnect_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        """Return whether there is a connection to the Apple TV."""
        return self.atv is not None

    @property
    def can_set_volume(self) -> bool:
        """Return whether the current audio output has a settable volume level.

        True for outputs like HomePod or AirPlay speakers. When the Apple TV
        controls the TV volume over HDMI-CEC it only supports volume up/down.
        """
        if self.atv is None:
            return False
        try:
            return self.atv.features.in_state(
                FeatureState.Available, FeatureName.Volume, FeatureName.SetVolume
            )
        except PYATV_ERRORS:
            return False

    async def async_connect(self) -> None:
        """Connect to the Apple TV.

        Raises CannotConnect when it can't be reached and ConfigEntryAuthFailed
        when it rejects the stored credentials.
        """
        host = self.config_entry.data[CONF_HOST]
        try:
            config = await async_scan_host(self.hass, host)
        except (*PYATV_ERRORS, OSError, ValueError) as err:
            raise CannotConnect(f"Scanning {host} failed: {err}") from err
        if config is None:
            raise CannotConnect(f"No Apple TV found at {host}")

        for protocol, credentials in self.config_entry.data.get(
            CONF_CREDENTIALS, {}
        ).items():
            config.set_credentials(Protocol[protocol], credentials)

        try:
            atv = await pyatv.connect(
                config, self.hass.loop, session=async_get_clientsession(self.hass)
            )
        except AUTH_ERRORS as err:
            raise ConfigEntryAuthFailed(
                f"{self.config_entry.title} rejected the stored credentials: {err}"
            ) from err
        except (*PYATV_ERRORS, OSError) as err:
            raise CannotConnect(f"Connecting to {host} failed: {err}") from err

        atv.listener = self
        atv.power.listener = self
        atv.audio.listener = self
        atv.push_updater.listener = self
        atv.push_updater.start()
        self._closing = False
        self.atv = atv
        await self._async_fetch_state()
        _LOGGER.debug("Connected to %s at %s", self.config_entry.title, host)

    async def async_disconnect(self) -> None:
        """Close the connection for good (entry unload)."""
        self._closing = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        atv, self.atv = self.atv, None
        if atv is None:
            return
        try:
            atv.push_updater.stop()
        except PYATV_ERRORS as err:
            _LOGGER.debug("Error stopping push updates: %s", err)
        await asyncio.gather(*atv.close(), return_exceptions=True)

    async def _async_update_data(self) -> AppleTvData:
        """Poll the state, reconnecting first if the connection was lost."""
        if self.atv is None:
            try:
                await self.async_connect()
            except CannotConnect as err:
                raise UpdateFailed(str(err)) from err
            return self.data

        await self._async_fetch_state()
        return self.data

    async def _async_fetch_state(self) -> None:
        """Read power state, now playing and app from the device."""
        if (atv := self.atv) is None:
            return
        try:
            self.data.power_state = atv.power.power_state
        except PYATV_ERRORS as err:
            _LOGGER.debug("Failed to read power state: %s", err)
        try:
            self.data.playing = await atv.metadata.playing()
            self.data.position_updated_at = dt_util.utcnow()
        except PYATV_ERRORS as err:
            _LOGGER.debug("Failed to read now playing: %s", err)
        try:
            self.data.volume = atv.audio.volume
        except PYATV_ERRORS as err:
            _LOGGER.debug("Failed to read volume: %s", err)
        self.data.app_name = self._current_app_name()

    def _current_app_name(self) -> str | None:
        """Return the name of the app in the foreground, if the device tells."""
        if self.atv is None:
            return None
        try:
            app = self.atv.metadata.app
        except PYATV_ERRORS:
            return None
        return app.name if app is not None else None

    # pyatv DeviceListener

    def connection_lost(self, exception: Exception) -> None:
        """Handle an unexpectedly lost connection."""
        _LOGGER.warning(
            "Connection to %s lost: %s", self.config_entry.title, exception
        )
        self._handle_disconnect()

    def connection_closed(self) -> None:
        """Handle a connection closed by the device."""
        if self._closing or self.atv is None:
            return
        _LOGGER.info("Connection to %s was closed", self.config_entry.title)
        self._handle_disconnect()

    # pyatv PushListener

    def playstatus_update(self, updater: PushUpdater, playstatus: Playing) -> None:
        """Handle a now playing update."""
        self.data.playing = playstatus
        self.data.position_updated_at = dt_util.utcnow()
        self.data.app_name = self._current_app_name()
        self.async_set_updated_data(self.data)

    def playstatus_error(self, updater: PushUpdater, exception: Exception) -> None:
        """Handle an error in the push updates (pyatv retries by itself)."""
        _LOGGER.debug("Push update error from %s: %s", self.config_entry.title, exception)

    # pyatv PowerListener

    def powerstate_update(self, old_state: PowerState, new_state: PowerState) -> None:
        """Handle a power state change."""
        self.data.power_state = new_state
        self.async_set_updated_data(self.data)

    # pyatv AudioListener

    def volume_update(self, old_level: float, new_level: float) -> None:
        """Handle a volume change."""
        self.data.volume = new_level
        self.async_set_updated_data(self.data)

    def volume_device_update(
        self, output_device: OutputDevice, old_level: float, new_level: float
    ) -> None:
        """Ignore volume changes of single output devices."""

    def outputdevices_update(
        self, old_devices: list[OutputDevice], new_devices: list[OutputDevice]
    ) -> None:
        """Rewrite the states: the volume capabilities can change with the output."""
        self.async_update_listeners()

    # Reconnection

    @callback
    def _handle_disconnect(self) -> None:
        """Drop the connection, mark entities unavailable and start reconnecting."""
        atv, self.atv = self.atv, None
        if atv is not None:
            atv.close()
        self.async_update_listeners()
        if self._closing or (
            self._reconnect_task is not None and not self._reconnect_task.done()
        ):
            return
        self._reconnect_task = self.config_entry.async_create_background_task(
            self.hass, self._async_reconnect(), f"Reconnect {self.config_entry.title}"
        )

    async def _async_reconnect(self) -> None:
        """Reconnect with exponential backoff; afterwards polling keeps retrying."""
        for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
            await asyncio.sleep(RECONNECT_DELAY * 2 ** (attempt - 1))
            if self._closing or self.atv is not None:
                return
            try:
                await self.async_connect()
            except CannotConnect as err:
                _LOGGER.debug(
                    "Reconnect attempt %d/%d to %s failed: %s",
                    attempt,
                    MAX_RECONNECT_ATTEMPTS,
                    self.config_entry.title,
                    err,
                )
                continue
            except ConfigEntryAuthFailed as err:
                _LOGGER.warning("%s", err)
                self.config_entry.async_start_reauth(self.hass)
                return
            _LOGGER.info("Reconnected to %s", self.config_entry.title)
            self.async_set_updated_data(self.data)
            return

        _LOGGER.warning(
            "Could not reconnect to %s, retrying every %d seconds",
            self.config_entry.title,
            UPDATE_INTERVAL,
        )
