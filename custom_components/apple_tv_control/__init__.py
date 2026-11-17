"""Apple TV Control integration for Home Assistant."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .coordinator import AppleTvConfigEntry, AppleTvCoordinator, CannotConnect


async def async_setup_entry(hass: HomeAssistant, entry: AppleTvConfigEntry) -> bool:
    """Set up Apple TV Control from a config entry."""
    coordinator = AppleTvCoordinator(hass, entry)
    try:
        await coordinator.async_connect()
    except CannotConnect as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AppleTvConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_disconnect()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: AppleTvConfigEntry) -> None:
    """Reload the entry when its options (the name) change."""
    await hass.config_entries.async_reload(entry.entry_id)
