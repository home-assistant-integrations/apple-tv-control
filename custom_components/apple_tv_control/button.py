"""Button platform for the Apple TV Control integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import pyatv.const

from .const import CONF_IDENTIFIER, DOMAIN
from .coordinator import AppleTvCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    identifier = config_entry.data[CONF_IDENTIFIER]
    name = config_entry.data.get("name", "Apple TV")

    async_add_entities(
        [
            AppleTvBackLongPressButton(config_entry, identifier, name),
            AppleTvTvLongPressButton(config_entry, identifier, name),
        ]
    )


class AppleTvBackLongPressButton(ButtonEntity):
    """Button entity for long-pressing the Back (Menu) button."""

    _attr_has_entity_name = True
    _attr_translation_key = "back_long_press"

    def __init__(
        self,
        config_entry: ConfigEntry,
        identifier: str,
        name: str,
    ) -> None:
        """Initialize the button."""
        self._config_entry = config_entry
        self._attr_unique_id = f"{identifier}_back_long_press"
        self._attr_name = f"{name} Back (Long Press)"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identifier)},
            "name": name,
            "manufacturer": "Apple Inc.",
            "model": "Apple TV",
        }

    @property
    def available(self) -> bool:
        """Return whether the button is available."""
        coordinator = _get_coordinator_for_entity_by_entry_id(
            self.hass, self._config_entry.entry_id
        )
        if coordinator is None:
            return False
        return coordinator.connected

    async def async_press(self) -> None:
        """Handle the button press."""
        coordinator = _get_coordinator_for_entity_by_entry_id(
            self.hass, self._config_entry.entry_id
        )
        if coordinator is None or not coordinator.connected:
            _LOGGER.warning("Apple TV not connected for %s", self._attr_name)
            return

        try:
            await coordinator.remote_control.menu(action=pyatv.const.InputAction.Hold)
            _LOGGER.debug("Sent back long press to %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to send back long press: %s", ex)


class AppleTvTvLongPressButton(ButtonEntity):
    """Button entity for long-pressing the TV (Home) button."""

    _attr_has_entity_name = True
    _attr_translation_key = "tv_long_press"

    def __init__(
        self,
        config_entry: ConfigEntry,
        identifier: str,
        name: str,
    ) -> None:
        """Initialize the button."""
        self._config_entry = config_entry
        self._attr_unique_id = f"{identifier}_tv_long_press"
        self._attr_name = f"{name} TV (Long Press)"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identifier)},
            "name": name,
            "manufacturer": "Apple Inc.",
            "model": "Apple TV",
        }

    @property
    def available(self) -> bool:
        """Return whether the button is available."""
        coordinator = _get_coordinator_for_entity_by_entry_id(
            self.hass, self._config_entry.entry_id
        )
        if coordinator is None:
            return False
        return coordinator.connected

    async def async_press(self) -> None:
        """Handle the button press."""
        coordinator = _get_coordinator_for_entity_by_entry_id(
            self.hass, self._config_entry.entry_id
        )
        if coordinator is None or not coordinator.connected:
            _LOGGER.warning("Apple TV not connected for %s", self._attr_name)
            return

        try:
            await coordinator.remote_control.home(action=pyatv.const.InputAction.Hold)
            _LOGGER.debug("Sent TV long press to %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to send TV long press: %s", ex)


def _get_coordinator_for_entity_by_entry_id(
    hass: HomeAssistant, entry_id: str
) -> AppleTvCoordinator | None:
    """Find the coordinator for a given config entry ID."""
    if entry_id in hass.data.get(DOMAIN, {}):
        return hass.data[DOMAIN][entry_id]
    return None
