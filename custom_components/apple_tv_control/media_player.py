"""Media player platform for the Apple TV Control integration."""

from __future__ import annotations

from datetime import datetime

from pyatv.const import DeviceState, PowerState
from pyatv.interface import AppleTV
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AppleTvConfigEntry, AppleTvCoordinator
from .entity import AppleTvEntity

SERVICE_NAVIGATE = "navigate"
SERVICE_SELECT = "select"
SERVICE_BACK = "back"
ATTR_DIRECTION = "direction"
DIRECTIONS = ["up", "down", "left", "right"]

DEVICE_STATES = {
    DeviceState.Playing: MediaPlayerState.PLAYING,
    DeviceState.Seeking: MediaPlayerState.PLAYING,
    DeviceState.Paused: MediaPlayerState.PAUSED,
    DeviceState.Loading: MediaPlayerState.BUFFERING,
    DeviceState.Stopped: MediaPlayerState.IDLE,
    DeviceState.Idle: MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AppleTvConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Apple TV media player and its remote control services."""
    async_add_entities([AppleTvMediaPlayer(config_entry.runtime_data)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_NAVIGATE,
        {vol.Required(ATTR_DIRECTION): vol.In(DIRECTIONS)},
        "async_navigate",
    )
    platform.async_register_entity_service(SERVICE_SELECT, {}, "async_select")
    platform.async_register_entity_service(SERVICE_BACK, {}, "async_back")


class AppleTvMediaPlayer(AppleTvEntity, MediaPlayerEntity):
    """Representation of an Apple TV media player."""

    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(self, coordinator: AppleTvCoordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, "media_player")
        self._volume_before_mute: float | None = None

    @property
    def state(self) -> MediaPlayerState:
        """Return the current state."""
        data = self.coordinator.data
        if data.power_state is PowerState.Off:
            return MediaPlayerState.OFF
        if data.playing is None:
            return MediaPlayerState.IDLE
        return DEVICE_STATES.get(data.playing.device_state, MediaPlayerState.IDLE)

    @property
    def media_title(self) -> str | None:
        """Return the title of the current media."""
        playing = self.coordinator.data.playing
        return playing.title if playing else None

    @property
    def media_artist(self) -> str | None:
        """Return the artist of the current media."""
        playing = self.coordinator.data.playing
        return playing.artist if playing else None

    @property
    def media_album_name(self) -> str | None:
        """Return the album of the current media."""
        playing = self.coordinator.data.playing
        return playing.album if playing else None

    @property
    def media_duration(self) -> int | None:
        """Return the duration of the current media in seconds."""
        playing = self.coordinator.data.playing
        return playing.total_time if playing else None

    @property
    def media_position(self) -> int | None:
        """Return the position of the current media in seconds."""
        playing = self.coordinator.data.playing
        return playing.position if playing else None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return when the position was last reported by the device."""
        return self.coordinator.data.position_updated_at

    @property
    def app_name(self) -> str | None:
        """Return the name of the app in the foreground."""
        return self.coordinator.data.app_name

    @property
    def is_volume_muted(self) -> bool:
        """Return whether the volume is muted by this entity."""
        return self._volume_before_mute is not None

    async def async_turn_on(self) -> None:
        """Turn the Apple TV on."""
        await self._async_send("turn on", lambda atv: atv.power.turn_on())

    async def async_turn_off(self) -> None:
        """Turn the Apple TV off."""
        await self._async_send("turn off", lambda atv: atv.power.turn_off())

    async def async_media_play(self) -> None:
        """Send play."""
        await self._async_send("play", lambda atv: atv.remote_control.play())

    async def async_media_pause(self) -> None:
        """Send pause."""
        await self._async_send("pause", lambda atv: atv.remote_control.pause())

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause."""
        await self._async_send(
            "toggle play/pause", lambda atv: atv.remote_control.play_pause()
        )

    async def async_media_stop(self) -> None:
        """Send stop."""
        await self._async_send("stop", lambda atv: atv.remote_control.stop())

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self._async_send("skip forward", lambda atv: atv.remote_control.next())

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self._async_send(
            "skip back", lambda atv: atv.remote_control.previous()
        )

    async def async_media_seek(self, position: float) -> None:
        """Seek to a position in seconds."""
        await self._async_send(
            "seek", lambda atv: atv.remote_control.set_position(round(position))
        )

    async def async_volume_up(self) -> None:
        """Turn the volume up."""
        await self._async_send("turn volume up", lambda atv: atv.audio.volume_up())

    async def async_volume_down(self) -> None:
        """Turn the volume down."""
        await self._async_send(
            "turn volume down", lambda atv: atv.audio.volume_down()
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute by setting the volume to 0 and restore it on unmute.

        pyatv has no mute command, so the previous volume is remembered here.
        """

        async def _set_mute(atv: AppleTV) -> None:
            if mute:
                if self._volume_before_mute is None:
                    self._volume_before_mute = atv.audio.volume
                await atv.audio.set_volume(0.0)
            elif self._volume_before_mute is not None:
                await atv.audio.set_volume(self._volume_before_mute)
                self._volume_before_mute = None

        await self._async_send("mute" if mute else "unmute", _set_mute)
        self.async_write_ha_state()

    async def async_navigate(self, direction: str) -> None:
        """Press a direction on the remote (service apple_tv_control.navigate)."""
        await self._async_send(
            f"navigate {direction}",
            lambda atv: getattr(atv.remote_control, direction)(),
        )

    async def async_select(self) -> None:
        """Press select on the remote (service apple_tv_control.select)."""
        await self._async_send("select", lambda atv: atv.remote_control.select())

    async def async_back(self) -> None:
        """Press back/menu on the remote (service apple_tv_control.back)."""
        await self._async_send("go back", lambda atv: atv.remote_control.menu())
