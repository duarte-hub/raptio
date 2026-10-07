"""Config flow for the RAPT integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import RaptApiError, RaptAuthError, RaptClient
from .const import (
    CONF_API_SECRET,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

SECRET_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL,
        max=MAX_SCAN_INTERVAL,
        step=10,
        unit_of_measurement="s",
        mode=NumberSelectorMode.BOX,
    )
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
        vol.Required(CONF_API_SECRET): SECRET_SELECTOR,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): INTERVAL_SELECTOR,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_SECRET): SECRET_SELECTOR})
OPTIONS_SCHEMA = vol.Schema({vol.Required(CONF_SCAN_INTERVAL): INTERVAL_SELECTOR})


class RaptioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a RAPT account from the UI."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RaptioOptionsFlow:
        return RaptioOptionsFlow()

    async def _async_validate(self, email: str, secret: str) -> dict[str, str]:
        client = RaptClient(async_get_clientsession(self.hass), email, secret)
        try:
            await client.async_authenticate()
        except RaptAuthError:
            return {"base": "invalid_auth"}
        except RaptApiError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            errors = await self._async_validate(email, user_input[CONF_API_SECRET])
            if not errors:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_API_SECRET: user_input[CONF_API_SECRET]},
                    options={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate(entry.data[CONF_EMAIL], user_input[CONF_API_SECRET])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_SECRET: user_input[CONF_API_SECRET]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )


class RaptioOptionsFlow(OptionsFlow):
    """Change the poll interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    CONF_SCAN_INTERVAL: self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    )
                },
            ),
        )
