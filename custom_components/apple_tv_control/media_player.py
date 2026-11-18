"""Media player platform for the Apple TV Control integration."""

from __future__ import annotations

from datetime import datetime

from pyatv.const import DeviceState, PowerState, Protocol
from pyatv.interface import AppleTV, RemoteControl
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AppleTvConfigEntry, AppleTvCoordinator
from .entity import AppleTvEntity

SERVICE_NAVIGATE = "navigate"
SERVICE_SELECT = "select"
SERVICE_BACK = "back"
ATTR_DIRECTION = "direction"
DIRECTIONS = ["up", "down", "left", "right"]

# Volume (percent) used for unmuting when the volume before muting is unknown
DEFAULT_UNMUTE_VOLUME = 30.0

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.VOLUME_STEP
)

DEVICE_STATES = {
    DeviceState.Playing: MediaPlayerState.PLAYING,
    DeviceState.Seeking: MediaPlayerState.PLAYING,
    DeviceState.Paused: MediaPlayerState.PAUSED,
    DeviceState.Loading: MediaPlayerState.BUFFERING,
    DeviceState.Stopped: MediaPlayerState.IDLE,
    DeviceState.Idle: MediaPlayerState.IDLE,
}


def _remote_buttons(atv: AppleTV) -> RemoteControl | None:
    """Return the remote control that presses buttons like the Siri Remote does.

    pyatv sends play and play/pause as MRP commands, which some apps ignore
    (waipu.tv does not resume on play). The Companion protocol presses the
    remote's play/pause button instead, like the remote in Control Center.
    pyatv prefers MRP, so the Companion remote control is taken from its
    facade; None when there is no Companion connection.
    """
    get_protocol = getattr(atv.remote_control, "get", None)
    if not callable(get_protocol):
        return None
    return get_protocol(Protocol.Companion)


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
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self, coordinator: AppleTvCoordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, "media_player")
        self._volume_before_mute: float | None = None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the features; mute needs an audio output with a volume level."""
        if self.coordinator.can_set_volume:
            return SUPPORTED_FEATURES | MediaPlayerEntityFeature.VOLUME_MUTE
        return SUPPORTED_FEATURES

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
        """Return whether the volume is at 0 (mute is emulated via the volume)."""
        return self.coordinator.can_set_volume and self.coordinator.data.volume == 0.0

    async def async_turn_on(self) -> None:
        """Turn the Apple TV on."""
        await self._async_send("turn on", lambda atv: atv.power.turn_on())

    async def async_turn_off(self) -> None:
        """Turn the Apple TV off."""
        await self._async_send("turn off", lambda atv: atv.power.turn_off())

    async def async_media_play(self) -> None:
        """Send play; resume paused media with the remote's play/pause button.

        The button toggles, so it is only pressed when the media is paused.
        """
        paused = self.state is MediaPlayerState.PAUSED

        async def _play(atv: AppleTV) -> None:
            if paused and (buttons := _remote_buttons(atv)) is not None:
                await buttons.play_pause()
            else:
                await atv.remote_control.play()

        await self._async_send("play", _play)

    async def async_media_pause(self) -> None:
        """Send pause."""
        await self._async_send("pause", lambda atv: atv.remote_control.pause())

    async def async_media_play_pause(self) -> None:
        """Press the remote's play/pause button."""
        await self._async_send(
            "toggle play/pause",
            lambda atv: (_remote_buttons(atv) or atv.remote_control).play_pause(),
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

        The Apple TV has no mute command, so this only works when its audio
        output has a settable volume level (see can_set_volume).
        """
        if not self.coordinator.can_set_volume:
            raise HomeAssistantError(
                f"{self.coordinator.config_entry.title} cannot be muted: with its "
                "current audio output the Apple TV only supports volume up and down"
            )

        async def _set_mute(atv: AppleTV) -> None:
            if mute:
                volume = atv.audio.volume
                await atv.audio.set_volume(0.0)
                if volume > 0.0:
                    self._volume_before_mute = volume
            else:
                await atv.audio.set_volume(
                    self._volume_before_mute or DEFAULT_UNMUTE_VOLUME
                )
                self._volume_before_mute = None

        await self._async_send("mute" if mute else "unmute", _set_mute)

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
