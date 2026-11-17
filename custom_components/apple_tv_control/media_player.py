"""Media player platform for Apple TV Control integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerEntityFeature as Feature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from pyatv.const import DeviceState, PowerState

from .const import CONF_IDENTIFIER, CONF_NAME, DOMAIN
from .coordinator import AppleTvCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Apple TV media player from a config entry."""
    coordinator: AppleTvCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AppleTvMediaPlayer(config_entry, coordinator)])


class AppleTvMediaPlayer(MediaPlayerEntity):
    """Representation of an Apple TV media player."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, config_entry: ConfigEntry, coordinator: AppleTvCoordinator
    ) -> None:
        """Initialize the Apple TV media player."""
        self.coordinator = coordinator
        self.config_entry = config_entry

        # Device info
        identifier = config_entry.data[CONF_IDENTIFIER]
        name = config_entry.data.get(CONF_NAME, "Apple TV")
        self._attr_unique_id = f"{identifier}_media_player"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=name,
            manufacturer="Apple Inc.",
            model="Apple TV",
        )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features flags."""
        return (
            Feature.TURN_ON
            | Feature.TURN_OFF
            | Feature.PLAY
            | Feature.PAUSE
            | Feature.STOP
            | Feature.PLAY_PAUSE
            | Feature.VOLUME_UP
            | Feature.VOLUME_DOWN
            | Feature.VOLUME_MUTE
            | Feature.PREVIOUS_TRACK
            | Feature.NEXT_TRACK
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state."""
        if not self.coordinator.connected:
            return MediaPlayerState.UNAVAILABLE

        power_state = self.coordinator.data.power_state
        if power_state == PowerState.Off:
            return MediaPlayerState.OFF

        # Device is on — check playing state
        playing = self.coordinator.data.playing
        if playing is not None:
            device_state = playing.device_state
            if device_state == DeviceState.Playing:
                return MediaPlayerState.PLAYING
            if device_state == DeviceState.Paused:
                return MediaPlayerState.PAUSED
            if device_state == DeviceState.Loading:
                return MediaPlayerState.BUFFERING
            if device_state == DeviceState.Stopped:
                return MediaPlayerState.IDLE

        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        playing = self.coordinator.data.playing
        if playing:
            return playing.title
        return None

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        playing = self.coordinator.data.playing
        if playing:
            return playing.artist
        return None

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        playing = self.coordinator.data.playing
        if playing:
            return playing.album
        return None

    @property
    def media_duration(self) -> int | None:
        """Return the duration of current playing media in seconds."""
        playing = self.coordinator.data.playing
        if playing and playing.total_time is not None:
            return playing.total_time
        return None

    @property
    def media_position(self) -> int | None:
        """Return the position of current playing media in seconds."""
        playing = self.coordinator.data.playing
        if playing and playing.position is not None:
            return playing.position
        return None

    @property
    def media_position_updated_at(self) -> Any:
        """Return the time when the position was last updated."""
        return dt_util.utcnow()

    @property
    def app_name(self) -> str | None:
        """Return the name of the current app."""
        return self.coordinator.data.app_name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the Apple TV."""
        if not self.coordinator.connected:
            _LOGGER.warning("Not connected to Apple TV, cannot turn on")
            return

        try:
            await self.coordinator.power.turn_on()
            await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error("Failed to turn on Apple TV: %s", ex)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the Apple TV."""
        if not self.coordinator.connected:
            _LOGGER.warning("Not connected to Apple TV, cannot turn off")
            return

        try:
            await self.coordinator.power.turn_off()
            await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error("Failed to turn off Apple TV: %s", ex)

    async def async_media_play(self) -> None:
        """Send play command."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.play()
        except Exception as ex:
            _LOGGER.error("Failed to send play command: %s", ex)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.pause()
        except Exception as ex:
            _LOGGER.error("Failed to send pause command: %s", ex)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.stop()
        except Exception as ex:
            _LOGGER.error("Failed to send stop command: %s", ex)

    async def async_media_play_pause(self) -> None:
        """Send play/pause toggle command."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.play_pause()
        except Exception as ex:
            _LOGGER.error("Failed to send play/pause command: %s", ex)

    async def async_volume_up(self) -> None:
        """Volume up the Apple TV."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.volume_up()
        except Exception as ex:
            _LOGGER.error("Failed to send volume up command: %s", ex)

    async def async_volume_down(self) -> None:
        """Volume down the Apple TV."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.volume_down()
        except Exception as ex:
            _LOGGER.error("Failed to send volume down command: %s", ex)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the Apple TV."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.mute()
        except Exception as ex:
            _LOGGER.error("Failed to send mute command: %s", ex)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.next()
        except Exception as ex:
            _LOGGER.error("Failed to send next track command: %s", ex)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.remote_control.previous()
        except Exception as ex:
            _LOGGER.error("Failed to send previous track command: %s", ex)

    async def async_update(self) -> None:
        """Update the entity state from the coordinator."""
        await self.coordinator.async_request_refresh()

    async def async_set_media_position(self, position: int) -> None:
        """Seek to a position in the media."""
        if not self.coordinator.connected:
            return

        try:
            await self.coordinator.metadata.seek(position * 1000)
        except Exception as ex:
            _LOGGER.error("Failed to seek: %s", ex)
