"""Tests for importing the legacy YAML sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import discogs_client
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.discogs.const import (
    CONF_EXCLUDED_SENSORS,
    CONF_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import MOCK_TOKEN


async def _setup_yaml(hass: HomeAssistant, **extra) -> None:
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": [{"platform": DOMAIN, "token": MOCK_TOKEN, **extra}]},
    )
    await hass.async_block_till_done()


async def test_import_default(
    hass: HomeAssistant, mock_discogs_client: MagicMock
) -> None:
    """A default YAML config keeps its old entity IDs and gets a repair issue."""
    await _setup_yaml(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Discogs"
    assert entries[0].data == {CONF_TOKEN: MOCK_TOKEN}
    assert entries[0].options == {}

    for entity_id in (
        "sensor.discogs_collection",
        "sensor.discogs_wantlist",
        "sensor.discogs_random_record",
    ):
        assert hass.states.get(entity_id) is not None, entity_id

    assert ir.async_get(hass).async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_import_name_interval_and_monitored_conditions(
    hass: HomeAssistant, mock_discogs_client: MagicMock
) -> None:
    """name, scan_interval and monitored_conditions all carry over."""
    await _setup_yaml(
        hass,
        name="My Records",
        scan_interval="00:30:00",
        monitored_conditions=["collection", "random_record"],
    )

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.title == "My Records"
    assert entry.options == {CONF_SCAN_INTERVAL_MINUTES: 30}
    assert entry.data[CONF_EXCLUDED_SENSORS] == ["wantlist"]

    # Legacy entity IDs were "<name> <sensor>" slugified.
    assert hass.states.get("sensor.my_records_collection") is not None
    assert hass.states.get("sensor.my_records_random_record") is not None
    # Excluded sensor exists in the registry but disabled, and has no state.
    reg = er.async_get(hass).async_get("sensor.my_records_wantlist")
    assert reg is not None
    assert reg.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get("sensor.my_records_wantlist") is None


async def test_import_already_configured(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """On later restarts the YAML is a no-op plus the deprecation issue."""
    mock_config_entry.add_to_hass(hass)
    await _setup_yaml(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert ir.async_get(hass).async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("side_effect", "issue"),
    [
        (
            discogs_client.exceptions.HTTPError("Unauthorized", 401),
            "deprecated_yaml_import_issue_invalid_auth",
        ),
        (
            discogs_client.exceptions.HTTPError("Server error", 503),
            "deprecated_yaml_import_issue_cannot_connect",
        ),
    ],
)
async def test_import_failure_issue(
    hass: HomeAssistant,
    mock_discogs_client: MagicMock,
    side_effect: Exception,
    issue: str,
) -> None:
    """A failed import creates an integration repair issue and no entry."""
    mock_discogs_client.identity.side_effect = side_effect
    await _setup_yaml(hass)
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue)
