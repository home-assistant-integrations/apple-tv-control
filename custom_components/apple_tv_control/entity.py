"""Base entity for the Apple TV Control integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pyatv.interface import AppleTV

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_IDENTIFIER, CONF_NAME, DEFAULT_NAME, DOMAIN, PYATV_ERRORS
from .coordinator import AppleTvCoordinator


class AppleTvEntity(CoordinatorEntity[AppleTvCoordinator]):
    """An entity of one Apple TV."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AppleTvCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        identifier = entry.data[CONF_IDENTIFIER]
        self._attr_unique_id = f"{identifier}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=entry.options.get(CONF_NAME) or entry.data.get(CONF_NAME, DEFAULT_NAME),
            manufacturer="Apple Inc.",
            model="Apple TV",
        )

    @property
    def available(self) -> bool:
        """Return whether the Apple TV is connected."""
        return super().available and self.coordinator.connected

    async def _async_send(
        self, action: str, command: Callable[[AppleTV], Awaitable[None]]
    ) -> None:
        """Send a command to the Apple TV, reporting failures to the user."""
        atv = self.coordinator.atv
        if atv is None:
            raise HomeAssistantError(
                f"Cannot {action}: {self.coordinator.config_entry.title} is not connected"
            )
        try:
            await command(atv)
        except PYATV_ERRORS as err:
            raise HomeAssistantError(f"Failed to {action}: {err}") from err
        except TimeoutError as err:
            raise HomeAssistantError(
                f"Failed to {action}: the Apple TV did not confirm the command"
            ) from err
