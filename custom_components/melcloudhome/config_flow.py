"""Config flow for MELCloud Home integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    BooleanSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError
from .const import CONF_DEBUG_MODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MELCloudHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for MELCloud Home."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            debug_mode = user_input.get(CONF_DEBUG_MODE, False)

            # Set unique ID to prevent duplicate accounts
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            # Validate credentials by attempting login
            client = None
            try:
                client = MELCloudHomeClient(debug_mode=debug_mode)
                await client.login(email, password)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                # Success - create entry
                title = "MELCloud Home (Debug)" if debug_mode else "MELCloud Home"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_DEBUG_MODE: debug_mode,
                    },
                )
            finally:
                # CRITICAL: Always close the client session to prevent memory leak
                if client is not None:
                    await client.close()

        # Show form
        # Build schema conditionally based on advanced mode
        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        }

        # Only show debug_mode if user has enabled Advanced Mode in their profile
        if self.show_advanced_options:
            schema_dict[vol.Optional(CONF_DEBUG_MODE, default=False)] = (
                BooleanSelector()
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow when credentials expire.

        This is called automatically by Home Assistant when the coordinator
        raises ConfigEntryAuthFailed (e.g., after power outage causes session expiry).

        Args:
            entry_data: Current config entry data (email, password, debug_mode)

        Returns:
            Flow result that shows reauth confirmation form
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation and collect new password.

        Args:
            user_input: User-provided password (or None to show form)

        Returns:
            Flow result (form with errors, or successful entry update)
        """
        errors: dict[str, str] = {}

        # Get current config entry using reauth helper
        entry = self._get_reauth_entry()

        if user_input is not None:
            email = entry.data[CONF_EMAIL]  # Keep existing email
            password = user_input[CONF_PASSWORD]

            # Validate new credentials
            client = None
            try:
                client = MELCloudHomeClient()
                await client.login(email, password)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except (TimeoutError, aiohttp.ClientError) as err:
                _LOGGER.debug("Connection error during reauth: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # Update config entry with new password (partial update)
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: password},
                )
            finally:
                # CRITICAL: Always close the client session to prevent memory leak
                if client is not None:
                    await client.close()

        # Show form with current email (read-only display)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration to update credentials."""
        errors: dict[str, str] = {}

        # Get current config entry using helper
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            email = entry.data[CONF_EMAIL]  # Keep existing email
            password = user_input[CONF_PASSWORD]

            # Validate new credentials
            client = None
            try:
                client = MELCloudHomeClient()
                await client.login(email, password)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except (TimeoutError, aiohttp.ClientError) as err:
                _LOGGER.debug("Connection error during reconfigure: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # Update config entry with new password (partial update)
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: password},
                )
            finally:
                # CRITICAL: Always close the client session to prevent memory leak
                if client is not None:
                    await client.close()

        # Show form with current email (read-only display)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
