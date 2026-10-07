"""Tests for the Discogs config and options flows."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import discogs_client
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests.exceptions import RequestException

from custom_components.discogs.const import CONF_SCAN_INTERVAL_MINUTES, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_TOKEN, MOCK_USER_ID


@pytest.fixture(autouse=True)
def skip_setup():
    """Don't actually set up entries created by the flow."""
    with patch("custom_components.discogs.async_setup_entry", return_value=True):
        yield


async def test_user_flow_default_name(
    hass: HomeAssistant, mock_discogs_client: MagicMock
) -> None:
    """The default name gives the legacy-compatible 'Discogs' title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN, CONF_NAME: "Discogs"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Discogs"
    assert result["data"] == {CONF_TOKEN: MOCK_TOKEN}
    assert result["result"].unique_id == str(MOCK_USER_ID)


async def test_user_flow_custom_name(
    hass: HomeAssistant, mock_discogs_client: MagicMock
) -> None:
    """A custom name becomes the entry title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN, CONF_NAME: "Vinyl"}
    )
    assert result["title"] == "Vinyl"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (discogs_client.exceptions.HTTPError("Unauthorized", 401), "invalid_auth"),
        (discogs_client.exceptions.HTTPError("Server error", 500), "cannot_connect"),
        (RequestException("boom"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors_then_recover(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    mock_identity: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Errors are shown on the form and the flow can recover."""
    mock_discogs_client.identity.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN, CONF_NAME: "Discogs"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_discogs_client.identity.side_effect = None
    mock_discogs_client.identity.return_value = mock_identity
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN, CONF_NAME: "Discogs"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same Discogs account can't be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: MOCK_TOKEN, CONF_NAME: "Discogs"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth stores the new token for the same account."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new_token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "new_token"


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    mock_identity: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A token for another account is refused during reauth."""
    mock_config_entry.add_to_hass(hass)
    mock_identity.id = 99999
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "other_token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_TOKEN] == MOCK_TOKEN


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The polling interval is stored as whole minutes."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL_MINUTES: 30.0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL_MINUTES: 30}


async def test_forms_serialize_for_frontend(
    hass: HomeAssistant,
    hass_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The user and options forms render through the real HTTP API.

    This catches a schema built with a library the running Home Assistant
    can't serialize (voluptuous vs probatio).
    """
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "config", {})
    client = await hass_client()

    resp = await client.post(
        "/api/config/config_entries/flow", json={"handler": DOMAIN}
    )
    assert resp.status == 200, await resp.text()
    names = [field["name"] for field in (await resp.json())["data_schema"]]
    assert names == [CONF_TOKEN, CONF_NAME]

    mock_config_entry.add_to_hass(hass)
    resp = await client.post(
        "/api/config/config_entries/options/flow",
        json={"handler": mock_config_entry.entry_id},
    )
    assert resp.status == 200, await resp.text()
    names = [field["name"] for field in (await resp.json())["data_schema"]]
    assert names == [CONF_SCAN_INTERVAL_MINUTES]
