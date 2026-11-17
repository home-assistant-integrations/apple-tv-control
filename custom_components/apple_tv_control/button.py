"""Button platform for the Apple TV Control integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pyatv.const import InputAction
from pyatv.interface import AppleTV

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AppleTvConfigEntry, AppleTvCoordinator
from .entity import AppleTvEntity


@dataclass(frozen=True, kw_only=True)
class AppleTvButtonDescription(ButtonEntityDescription):
    """Describes an Apple TV button."""

    press_fn: Callable[[AppleTV], Awaitable[None]]


BUTTONS = (
    AppleTvButtonDescription(
        key="back_long_press",
        translation_key="back_long_press",
        press_fn=lambda atv: atv.remote_control.menu(action=InputAction.Hold),
    ),
    AppleTvButtonDescription(
        key="tv_long_press",
        translation_key="tv_long_press",
        press_fn=lambda atv: atv.remote_control.home(action=InputAction.Hold),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AppleTvConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the long press buttons."""
    coordinator = config_entry.runtime_data
    async_add_entities(AppleTvButton(coordinator, description) for description in BUTTONS)


class AppleTvButton(AppleTvEntity, ButtonEntity):
    """A long press of an Apple TV remote button."""

    entity_description: AppleTvButtonDescription

    def __init__(
        self, coordinator: AppleTvCoordinator, description: AppleTvButtonDescription
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the long press."""
        await self._async_send(
            f"long press {self.entity_description.key}", self.entity_description.press_fn
        )
