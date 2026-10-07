"""Tests for the Discogs sensors and coordinator."""

from __future__ import annotations

from datetime import timedelta
from json import JSONDecodeError
from unittest.mock import MagicMock

import discogs_client
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from requests.exceptions import RequestException

from custom_components.discogs.const import CONF_SCAN_INTERVAL_MINUTES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import MOCK_USER_ID, MOCK_USERNAME


async def test_entities_and_ids(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Default name yields the same entity IDs the YAML sensors had."""
    assert setup_integration.state is ConfigEntryState.LOADED

    collection = hass.states.get("sensor.discogs_collection")
    wantlist = hass.states.get("sensor.discogs_wantlist")
    record = hass.states.get("sensor.discogs_random_record")
    assert collection.state == "42"
    assert collection.attributes["unit_of_measurement"] == "records"
    assert collection.attributes["identity"] == MOCK_USERNAME
    assert wantlist.state == "10"
    assert record.state == "Artist Name - Album Title"
    assert record.attributes["cat_no"] == "CAT001"
    assert record.attributes["cover_image"] == "https://example.com/cover.jpg"
    assert record.attributes["format"] == "Vinyl (LP)"
    assert record.attributes["label"] == "Label Name"
    assert record.attributes["released"] == "2023"
    assert record.attributes["identity"] == MOCK_USERNAME

    registry = er.async_get(hass)
    entry = registry.async_get("sensor.discogs_random_record")
    assert entry.unique_id == f"{MOCK_USER_ID}_random_record"


async def test_one_fetch_per_refresh(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_discogs_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """All three sensors share one identity() call per poll (1.0.2 fix)."""
    assert mock_discogs_client.identity.call_count == 1
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_discogs_client.identity.call_count == 2


async def test_update_entity_forces_new_pick(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_discogs_client: MagicMock,
    mock_discogs_data: dict,
) -> None:
    """homeassistant.update_entity (the extras refresh script) re-picks."""
    mock_discogs_data["title"] = "Another Title"
    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": "sensor.discogs_random_record"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_discogs_client.identity.call_count == 2
    assert hass.states.get("sensor.discogs_random_record").state == (
        "Artist Name - Another Title"
    )


async def test_transient_error_keeps_last_values(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_discogs_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Throttled/garbled responses keep the last known values (1.0.2 behavior)."""
    for err in (
        JSONDecodeError("bad", "", 0),
        RequestException("boom"),
        discogs_client.exceptions.HTTPError("Too Many Requests", 429),
    ):
        mock_discogs_client.identity.side_effect = err
        freezer.tick(timedelta(hours=1, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get("sensor.discogs_collection").state == "42"
        assert hass.states.get("sensor.discogs_random_record").state == (
            "Artist Name - Album Title"
        )


async def test_random_record_failure_keeps_previous_pick(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_identity: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed release fetch keeps the previous record but updates counts."""
    mock_identity.num_collection = 43
    mock_identity.collection_folders[
        0
    ].releases.__getitem__.side_effect = RequestException("boom")
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.discogs_collection").state == "43"
    assert hass.states.get("sensor.discogs_random_record").state == (
        "Artist Name - Album Title"
    )


async def test_first_refresh_failure_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discogs_client: MagicMock,
) -> None:
    """With nothing to fall back on, setup is retried later."""
    mock_discogs_client.identity.side_effect = RequestException("boom")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_discogs_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A rejected token triggers the reauth flow."""
    mock_discogs_client.identity.side_effect = discogs_client.exceptions.HTTPError(
        "Unauthorized", 401
    )
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_empty_collection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discogs_client: MagicMock,
    mock_identity: MagicMock,
) -> None:
    """An empty collection gives an unknown random record, not an error."""
    mock_identity.collection_folders[0].count = 0
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    record = hass.states.get("sensor.discogs_random_record")
    assert record.state == "unknown"
    assert record.attributes["identity"] == MOCK_USERNAME


async def test_sparse_release_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discogs_client: MagicMock,
    mock_discogs_data: dict,
) -> None:
    """Releases without format descriptions don't break the attributes."""
    mock_discogs_data["formats"] = [{"name": "CD"}]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.discogs_random_record").attributes["format"] == "CD"


async def test_options_change_interval(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_discogs_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Changing the option reloads with the new polling interval."""
    hass.config_entries.async_update_entry(
        setup_integration, options={CONF_SCAN_INTERVAL_MINUTES: 15}
    )
    await hass.async_block_till_done()
    calls = mock_discogs_client.identity.call_count
    freezer.tick(timedelta(minutes=15, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_discogs_client.identity.call_count == calls + 1


async def test_unload(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """The entry unloads cleanly."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    assert setup_integration.state is ConfigEntryState.NOT_LOADED
