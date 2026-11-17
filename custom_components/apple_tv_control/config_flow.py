"""Config flow for Apple TV Control integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

import pyatv
from pyatv.const import Protocol
from pyatv.exceptions import PyatvError
from pyatv.interface import BaseConfig, PairingHandler

from .const import (
    CONF_COMPANION_CREDENTIALS,
    CONF_HOST,
    CONF_IDENTIFIER,
    CONF_MRP_CREDENTIALS,
    CONF_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"
CONF_PIN = "pin"

MRP_PROTOCOL = Protocol.MRP
COMPANION_PROTOCOL = Protocol.Companion


class AppleTvConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Apple TV Control."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, BaseConfig] = {}
        self._selected_config: BaseConfig | None = None
        self._pairing: PairingHandler | None = None
        self._mrp_credentials: str | None = None
        self._companion_credentials: str | None = None
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                loop = asyncio.get_running_loop()
                devices = await pyatv.scan(
                    loop, hosts=[host], protocol=MRP_PROTOCOL
                )
                if not devices:
                    errors["base"] = "cannot_connect"
                else:
                    config = devices[0]
                    await self.async_set_unique_id(config.identifier)
                    self._abort_if_unique_id_configured()
                    self._selected_config = config
                    return await self._async_start_pairing(MRP_PROTOCOL)
            except (PyatvError, OSError) as ex:
                _LOGGER.debug("Failed to connect to %s: %s", host, ex)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        # Scan for all Apple TV devices on the network
        try:
            loop = asyncio.get_running_loop()
            devices = await pyatv.scan(loop)
        except (PyatvError, OSError):
            return self.async_abort(reason="no_devices_found")

        if not devices:
            return self.async_abort(reason="no_devices_found")

        # Build a list of devices for selection
        self._discovered_devices = {
            f"{config.name} ({config.address})": config for config in devices
        }

        # Check if any are already configured
        configured_identifiers = {
            entry.data.get(CONF_IDENTIFIER)
            for entry in self._async_current_entries()
            if entry.data.get(CONF_IDENTIFIER)
        }

        available_devices = {
            name: config
            for name, config in self._discovered_devices.items()
            if config.identifier not in configured_identifiers
        }

        if not available_devices:
            return self.async_abort(reason="already_configured")

        self._discovered_devices = available_devices

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(
                        list(self._discovered_devices.keys())
                    ),
                }
            ),
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection from discovery."""
        if user_input is not None:
            device_name = user_input[CONF_DEVICE]
            config = self._discovered_devices[device_name]

            await self.async_set_unique_id(config.identifier)
            self._abort_if_unique_id_configured()

            self._selected_config = config

            # Check if MRP credentials already exist
            mrp_service = config.get_service(MRP_PROTOCOL)
            if mrp_service and mrp_service.credentials:
                self._mrp_credentials = mrp_service.credentials

            # Try MRP pairing if no credentials
            if not self._mrp_credentials:
                return await self._async_start_pairing(MRP_PROTOCOL)

            # Try Companion pairing
            companion_service = config.get_service(COMPANION_PROTOCOL)
            if companion_service and not companion_service.credentials:
                return await self._async_start_pairing(COMPANION_PROTOCOL)

            # Already have credentials, create entry
            return self._async_create_entry()

        # If no input yet, show the discovery form (should already be shown)
        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(
                        list(self._discovered_devices.keys())
                    ),
                }
            ),
        )

    async def _async_start_pairing(
        self, protocol: Protocol
    ) -> ConfigFlowResult:
        """Start pairing with the specified protocol."""
        if not self._selected_config:
            raise AbortFlow("no_device_selected")

        protocol_name = "Companion" if protocol == COMPANION_PROTOCOL else "MRP"

        try:
            loop = asyncio.get_running_loop()
            self._pairing = await pyatv.pair(
                self._selected_config, protocol, loop
            )
        except PyatvError as ex:
            _LOGGER.debug("Pairing not available for %s: %s", protocol_name, ex)
            if protocol == COMPANION_PROTOCOL:
                return self._async_create_entry()
            return self.async_abort(reason="pairing_failed")

        try:
            await self._pairing.begin()
        except PyatvError as ex:
            _LOGGER.debug("Pairing begin failed for %s: %s", protocol_name, ex)
            if self._pairing:
                await self._pairing.close()
            if protocol == COMPANION_PROTOCOL:
                return self._async_create_entry()
            return self.async_abort(reason="pairing_failed")

        # Show PIN form
        if self._pairing.device_provides_pin:
            pin_placeholder = "Enter the PIN code displayed on your Apple TV."
        else:
            pin_placeholder = (
                f"Enter this PIN code on your Apple TV: {self._pairing.pin_code}"
            )

        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): str,
                }
            ),
            description_placeholders={
                "protocol": protocol_name,
                "pin": pin_placeholder,
            },
        )

    async def async_step_pair(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle PIN entry during pairing."""
        errors: dict[str, str] = {}

        if not self._pairing:
            raise AbortFlow("pairing_not_started")

        pin = user_input[CONF_PIN]

        try:
            self._pairing.pin(pin)
            await self._pairing.finish()

            if self._pairing.has_paired:
                credentials = self._pairing.service.credentials

                # Determine which protocol was paired
                if self._pairing.service.protocol == MRP_PROTOCOL:
                    self._mrp_credentials = credentials
                    # Try Companion pairing next
                    companion_service = self._selected_config.get_service(
                        COMPANION_PROTOCOL
                    )
                    if companion_service:
                        return await self._async_start_pairing(COMPANION_PROTOCOL)
                    return self._async_create_entry()
                if self._pairing.service.protocol == COMPANION_PROTOCOL:
                    self._companion_credentials = credentials
                    return self._async_create_entry()
            else:
                errors["base"] = "pairing_failed"

        except PyatvError as ex:
            _LOGGER.debug("Pairing failed: %s", ex)
            errors["base"] = "invalid_pin"

        if self._pairing:
            await self._pairing.close()
            self._pairing = None

        if errors:
            if errors["base"] == "invalid_pin":
                # Restart pairing
                protocol = (
                    COMPANION_PROTOCOL
                    if self._mrp_credentials
                    else MRP_PROTOCOL
                )
                return await self._async_start_pairing(protocol)
            return self.async_abort(reason="pairing_failed")

        return self._async_create_entry()

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if not self._reauth_entry:
            raise AbortFlow("reauth_entry_not_found")

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth confirmation."""
        errors: dict[str, str] = {}

        if not self._reauth_entry:
            raise AbortFlow("reauth_entry_not_found")

        host = self._reauth_entry.data.get(CONF_HOST)
        identifier = self._reauth_entry.data.get(CONF_IDENTIFIER)

        if user_input is not None:
            host = user_input.get(CONF_HOST, host)

            try:
                loop = asyncio.get_running_loop()
                devices = await pyatv.scan(
                    loop, hosts=[host], protocol=MRP_PROTOCOL
                )
                if not devices:
                    errors["base"] = "cannot_connect"
                else:
                    config = devices[0]
                    if identifier:
                        await self.async_set_unique_id(identifier)
                    else:
                        await self.async_set_unique_id(config.identifier)
                    self._selected_config = config
                    return await self._async_start_pairing(MRP_PROTOCOL)
            except (PyatvError, OSError) as ex:
                _LOGGER.debug("Failed to reconnect to %s: %s", host, ex)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host or ""): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "name": self._reauth_entry.data.get(CONF_NAME, "Apple TV"),
            },
        )

    def _async_create_entry(self) -> ConfigFlowResult:
        """Create the config entry with collected data."""
        if not self._selected_config:
            raise AbortFlow("no_device_selected")

        config = self._selected_config

        data = {
            CONF_IDENTIFIER: config.identifier,
            CONF_HOST: config.address,
            CONF_NAME: config.name,
            CONF_MRP_CREDENTIALS: self._mrp_credentials,
            CONF_COMPANION_CREDENTIALS: self._companion_credentials,
        }

        return self.async_create_entry(
            title=config.name,
            data=data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AppleTvOptionsFlow:
        """Get the options flow for this handler."""
        return AppleTvOptionsFlow(config_entry)


class AppleTvOptionsFlow(OptionsFlow):
    """Handle options flow for Apple TV Control."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.config_entry.data.get(CONF_NAME, "")
                    ): str,
                }
            ),
        )
