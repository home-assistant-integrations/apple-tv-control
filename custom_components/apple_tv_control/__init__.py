"""Apple TV Control integration for Home Assistant."""

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import AppleTvCoordinator, async_setup_coordinator

_LOGGER = logging.getLogger(__name__)

# Config schema for async_setup (UI-only config)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Service direction constants
DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
DIRECTION_LEFT = "left"
DIRECTION_RIGHT = "right"
VALID_DIRECTIONS = [DIRECTION_UP, DIRECTION_DOWN, DIRECTION_LEFT, DIRECTION_RIGHT]

SERVICE_NAVIGATE = "navigate"
SERVICE_SELECT = "select"
SERVICE_BACK = "back"

# Schemas for services that target entities (entity_id/device_id/area_id)
ENTITY_SERVICE_SCHEMA = cv.make_entity_service_schema({})

NAVIGATE_SERVICE_SCHEMA = cv.make_entity_service_schema(
    {vol.Required("direction"): vol.In(VALID_DIRECTIONS)}
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Apple TV Control integration."""
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Apple TV Control from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    coordinator = await async_setup_coordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.disconnect()

    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register navigation services."""

    async def _async_coordinators(
        call: ServiceCall,
    ) -> list[tuple[str, AppleTvCoordinator]]:
        """Resolve the service call target to connected coordinators."""
        result = []
        for entity_id in await async_extract_entity_ids(call):
            coordinator = _get_coordinator_for_entity(hass, entity_id)
            if coordinator is None or not coordinator.connected:
                _LOGGER.warning("Apple TV not connected for entity %s", entity_id)
                continue
            result.append((entity_id, coordinator))
        return result

    async def _async_handle_navigate(call: ServiceCall) -> None:
        """Handle the navigate service call."""
        direction = call.data["direction"]
        for entity_id, coordinator in await _async_coordinators(call):
            try:
                await getattr(coordinator.remote_control, direction)()
            except Exception as ex:
                _LOGGER.error(
                    "Failed to navigate %s on %s: %s", direction, entity_id, ex
                )

    async def _async_handle_select(call: ServiceCall) -> None:
        """Handle the select service call."""
        for entity_id, coordinator in await _async_coordinators(call):
            try:
                await coordinator.remote_control.select()
            except Exception as ex:
                _LOGGER.error("Failed to send select to %s: %s", entity_id, ex)

    async def _async_handle_back(call: ServiceCall) -> None:
        """Handle the back service call."""
        for entity_id, coordinator in await _async_coordinators(call):
            try:
                await coordinator.remote_control.menu()
            except Exception as ex:
                _LOGGER.error("Failed to send back to %s: %s", entity_id, ex)

    hass.services.async_register(
        DOMAIN,
        SERVICE_NAVIGATE,
        _async_handle_navigate,
        schema=NAVIGATE_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT,
        _async_handle_select,
        schema=ENTITY_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BACK,
        _async_handle_back,
        schema=ENTITY_SERVICE_SCHEMA,
    )


def _get_coordinator_for_entity(
    hass: HomeAssistant, entity_id: str
) -> AppleTvCoordinator | None:
    """Find the coordinator for a given entity ID."""
    entity_reg = er.async_get(hass)
    entity_entry = entity_reg.entities.get(entity_id)
    if entity_entry is None:
        return None

    entry_id = entity_entry.config_entry_id
    if entry_id and entry_id in hass.data.get(DOMAIN, {}):
        return hass.data[DOMAIN][entry_id]
    return None
