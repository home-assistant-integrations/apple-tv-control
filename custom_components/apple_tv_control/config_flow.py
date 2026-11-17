"""Config flow for Apple TV Control integration."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
import logging
from random import randrange
from typing import TYPE_CHECKING, Any

import pyatv
from pyatv.const import PairingRequirement, Protocol
from pyatv.interface import BaseConfig, PairingHandler
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CREDENTIALS,
    CONF_HOST,
    CONF_IDENTIFIER,
    CONF_NAME,
    DOMAIN,
    PYATV_ERRORS,
)
from .coordinator import async_scan_host

if TYPE_CHECKING:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

_LOGGER = logging.getLogger(__name__)

CONF_PIN = "pin"

# Name the Apple TV shows for the paired client
PAIRING_NAME = "Home Assistant"


class AppleTvConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Apple TV Control."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: BaseConfig | None = None
        self._protocols: deque[Protocol] = deque()
        self._protocol: Protocol | None = None
        self._pairing: PairingHandler | None = None
        self._pin: int | None = None
        self._credentials: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            config = await self._async_scan(user_input[CONF_HOST])
            if config is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(config.identifier)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: str(config.address)}
                )
                return await self._async_start_pairing(config)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle an Apple TV found by zeroconf discovery."""
        host = discovery_info.host
        self._async_abort_entries_match({CONF_HOST: host})

        config = await self._async_scan(host)
        if config is None:
            return self.async_abort(reason="no_devices_found")

        await self.async_set_unique_id(config.identifier)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._config = config
        self.context["title_placeholders"] = {"name": config.name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm setting up a discovered Apple TV."""
        assert self._config is not None
        if user_input is not None:
            return await self._async_start_pairing(self._config)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._config.name},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle rejected credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pair the Apple TV of an existing entry again."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            config = await self._async_scan(user_input[CONF_HOST])
            if config is None:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(config.identifier)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return await self._async_start_pairing(config)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    async def async_step_pair_with_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the PIN code the Apple TV shows."""
        assert self._config is not None and self._protocol is not None
        assert self._pairing is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            self._pairing.pin(user_input[CONF_PIN])
            try:
                await self._pairing.finish()
            except PYATV_ERRORS as err:
                _LOGGER.debug("Pairing %s failed: %s", self._protocol.name, err)
            if self._pairing.has_paired:
                return await self._async_save_credentials()
            errors["base"] = "invalid_pin"

        return self.async_show_form(
            step_id="pair_with_pin",
            data_schema=vol.Schema({vol.Required(CONF_PIN): str}),
            errors=errors,
            description_placeholders={
                "name": self._config.name,
                "protocol": self._protocol.name,
            },
        )

    async def async_step_pair_no_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show a PIN code the user enters on the Apple TV."""
        assert self._config is not None and self._protocol is not None
        assert self._pairing is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._pairing.finish()
            except PYATV_ERRORS as err:
                _LOGGER.debug("Pairing %s failed: %s", self._protocol.name, err)
            if self._pairing.has_paired:
                return await self._async_save_credentials()
            errors["base"] = "pairing_failed"

        return self.async_show_form(
            step_id="pair_no_pin",
            errors=errors,
            description_placeholders={
                "name": self._config.name,
                "protocol": self._protocol.name,
                "pin": str(self._pin),
            },
        )

    async def _async_scan(self, host: str) -> BaseConfig | None:
        """Scan one host, returning None if no Apple TV answers."""
        try:
            return await async_scan_host(self.hass, host)
        except (*PYATV_ERRORS, OSError, ValueError) as err:
            _LOGGER.debug("Scanning %s failed: %s", host, err)
            return None

    async def _async_start_pairing(self, config: BaseConfig) -> ConfigFlowResult:
        """Pair every protocol of the device that needs it, one after another."""
        self._config = config
        self._credentials = {}
        self._protocols = deque(
            service.protocol for service in config.services if service.enabled
        )
        return await self._async_pair_next_protocol()

    async def _async_pair_next_protocol(self) -> ConfigFlowResult:
        """Start pairing the next protocol, or finish when none is left."""
        assert self._config is not None
        await self._async_close_pairing()

        while self._protocols:
            protocol = self._protocols.popleft()
            service = self._config.get_service(protocol)
            if service is None or service.pairing in (
                PairingRequirement.Unsupported,
                PairingRequirement.NotNeeded,
            ):
                continue
            if service.pairing is PairingRequirement.Disabled:
                _LOGGER.warning(
                    "Pairing %s is disabled on %s, allow access in the Apple TV's "
                    "AirPlay settings to use all features",
                    protocol.name,
                    self._config.name,
                )
                continue
            if protocol is Protocol.DMAP or service.requires_password:
                _LOGGER.warning(
                    "Skipping %s on %s: legacy DMAP and password protected services "
                    "are not supported",
                    protocol.name,
                    self._config.name,
                )
                continue

            pair_args: dict[str, Any] = {}
            if protocol in (Protocol.AirPlay, Protocol.Companion):
                pair_args["name"] = PAIRING_NAME
            self._protocol = protocol
            self._pairing = await pyatv.pair(
                self._config,
                protocol,
                self.hass.loop,
                session=async_get_clientsession(self.hass),
                **pair_args,
            )
            try:
                await self._pairing.begin()
            except PYATV_ERRORS as err:
                _LOGGER.warning(
                    "Could not start %s pairing with %s: %s",
                    protocol.name,
                    self._config.name,
                    err,
                )
                await self._async_close_pairing()
                if service.pairing is PairingRequirement.Optional:
                    continue
                return self.async_abort(reason="pairing_failed")

            if self._pairing.device_provides_pin:
                return await self.async_step_pair_with_pin()
            self._pin = randrange(1000, 10000)
            self._pairing.pin(self._pin)
            return await self.async_step_pair_no_pin()

        return await self._async_finish()

    async def _async_save_credentials(self) -> ConfigFlowResult:
        """Keep the credentials of the protocol that was just paired."""
        assert self._pairing is not None and self._protocol is not None
        credentials = self._pairing.service.credentials
        if credentials:
            self._credentials[self._protocol.name] = credentials
        return await self._async_pair_next_protocol()

    async def _async_finish(self) -> ConfigFlowResult:
        """Create the entry, or update it when re-pairing."""
        assert self._config is not None
        host = str(self._config.address)

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={CONF_HOST: host, CONF_CREDENTIALS: self._credentials},
            )

        return self.async_create_entry(
            title=self._config.name,
            data={
                CONF_IDENTIFIER: self._config.identifier,
                CONF_HOST: host,
                CONF_NAME: self._config.name,
                CONF_CREDENTIALS: self._credentials,
            },
        )

    async def _async_close_pairing(self) -> None:
        """Close a running pairing session."""
        if self._pairing is not None:
            await self._pairing.close()
            self._pairing = None

    @callback
    def async_remove(self) -> None:
        """Close a running pairing session when the flow is cancelled."""
        if self._pairing is not None:
            self.hass.async_create_task(self._async_close_pairing())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AppleTvOptionsFlow:
        """Get the options flow for this handler."""
        return AppleTvOptionsFlow()


class AppleTvOptionsFlow(OptionsFlow):
    """Handle options flow for Apple TV Control."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user override the device name."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        name = self.config_entry.options.get(
            CONF_NAME, self.config_entry.data.get(CONF_NAME, "")
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_NAME, default=name): str}),
        )
