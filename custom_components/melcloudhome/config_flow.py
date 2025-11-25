"""Config flow for MELCloud Home integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError
from .const import DOMAIN

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

            # Set unique ID to prevent duplicate accounts
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            # Validate credentials by attempting login
            try:
                client = MELCloudHomeClient()
                await client.login(email, password)
                await client.close()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                # Success - create entry
                return self.async_create_entry(
                    title="MELCloud Home",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
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
            try:
                client = MELCloudHomeClient()
                await client.login(email, password)
                await client.close()
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
