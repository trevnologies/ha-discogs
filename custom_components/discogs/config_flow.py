"""Config flow for the Discogs integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

import discogs_client
from requests.exceptions import RequestException

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .compat import flow_vol as vol
from .const import (
    CONF_EXCLUDED_SENSORS,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)

TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): TOKEN_SELECTOR,
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): TOKEN_SELECTOR})


def _validate_token(token: str) -> tuple[int | None, str, dict[str, str]]:
    """Validate the token and return the user ID, username, and errors."""
    errors: dict[str, str] = {}
    user_id: int | None = None
    username = ""
    try:
        client = discogs_client.Client(SERVER_SOFTWARE, user_token=token)
        identity = client.identity()
        user_id = identity.id
        username = identity.name
    except discogs_client.exceptions.HTTPError as err:
        if getattr(err, "status_code", None) == 401:
            errors["base"] = "invalid_auth"
        else:
            errors["base"] = "cannot_connect"
    except RequestException:
        errors["base"] = "cannot_connect"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected error validating Discogs token")
        errors["base"] = "unknown"
    return user_id, username, errors


def _interval_to_minutes(value: timedelta | None) -> int | None:
    """Convert a YAML scan_interval into whole minutes within allowed range."""
    if value is None:
        return None
    minutes = round(value.total_seconds() / 60)
    return max(MIN_SCAN_INTERVAL_MINUTES, min(MAX_SCAN_INTERVAL_MINUTES, minutes))


class DiscogsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discogs."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DiscogsOptionsFlow:
        """Return the options flow handler."""
        return DiscogsOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id, _, errors = await self.hass.async_add_executor_job(
                _validate_token, user_input[CONF_TOKEN]
            )
            if not errors:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={CONF_TOKEN: user_input[CONF_TOKEN]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a legacy `sensor: - platform: discogs` YAML configuration."""
        user_id, _, errors = await self.hass.async_add_executor_job(
            _validate_token, import_data[CONF_TOKEN]
        )
        if errors:
            return self.async_abort(reason=errors["base"])
        await self.async_set_unique_id(str(user_id))
        self._abort_if_unique_id_configured()

        options: dict[str, Any] = {}
        minutes = _interval_to_minutes(import_data.get(CONF_SCAN_INTERVAL))
        if minutes is not None:
            options[CONF_SCAN_INTERVAL_MINUTES] = minutes

        data: dict[str, Any] = {CONF_TOKEN: import_data[CONF_TOKEN]}
        if excluded := import_data.get(CONF_EXCLUDED_SENSORS):
            data[CONF_EXCLUDED_SENSORS] = list(excluded)

        return self.async_create_entry(
            title=import_data.get(CONF_NAME) or DEFAULT_NAME,
            data=data,
            options=options,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after Discogs rejected the token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id, _, errors = await self.hass.async_add_executor_job(
                _validate_token, user_input[CONF_TOKEN]
            )
            if not errors:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_TOKEN: user_input[CONF_TOKEN]},
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )


class DiscogsOptionsFlow(OptionsFlow):
    """Handle Discogs options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the polling interval."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL_MINUTES: int(
                        user_input[CONF_SCAN_INTERVAL_MINUTES]
                    )
                }
            )

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES,
            int(DEFAULT_SCAN_INTERVAL.total_seconds() // 60),
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES, default=current
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MINUTES,
                        max=MAX_SCAN_INTERVAL_MINUTES,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
