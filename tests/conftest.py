"""Fixtures for the Discogs custom integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from awesomeversion import AwesomeVersion
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.discogs.const import DOMAIN
from homeassistant.const import CONF_TOKEN, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant

from . import MOCK_TOKEN, MOCK_USER_ID

pytest_plugins = "pytest_homeassistant_custom_component"

# The integration needs Home Assistant 2026.11 (setup and unload return None,
# which older releases read as a failed setup). Until the test harness ships
# a 2026.11 release, an older harness skips the suite instead of failing it.
MIN_HA_VERSION = AwesomeVersion("2026.11.0")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip every test on a Home Assistant release older than the minimum."""
    if AwesomeVersion(HA_VERSION) >= MIN_HA_VERSION:
        return
    skip = pytest.mark.skip(
        reason=f"needs Home Assistant {MIN_HA_VERSION} or later, harness has {HA_VERSION}"
    )
    for item in items:
        item.add_marker(skip)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry as the UI flow creates it with the default name."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Discogs",
        data={CONF_TOKEN: MOCK_TOKEN},
        unique_id=str(MOCK_USER_ID),
    )


@pytest.fixture
def mock_discogs_data() -> dict:
    """Return Discogs basic_information for a release."""
    return {
        "artists": [{"name": "Artist Name"}],
        "title": "Album Title",
        "labels": [{"catno": "CAT001", "name": "Label Name"}],
        "cover_image": "https://example.com/cover.jpg",
        "formats": [{"name": "Vinyl", "descriptions": ["LP", "Album"]}],
        "year": "2023",
    }


@pytest.fixture
def mock_identity(mock_discogs_data: dict) -> MagicMock:
    """Return a mock Discogs identity."""
    from . import MOCK_USERNAME

    identity = MagicMock()
    identity.id = MOCK_USER_ID
    identity.name = MOCK_USERNAME
    identity.num_collection = 42
    identity.num_wantlist = 10

    release = MagicMock()
    release.release.data = mock_discogs_data
    folder = MagicMock()
    folder.count = 42
    folder.releases.__getitem__ = MagicMock(return_value=release)
    identity.collection_folders = [folder]
    return identity


@pytest.fixture
def mock_discogs_client(mock_identity: MagicMock) -> Generator[MagicMock]:
    """Patch the Discogs client everywhere the integration creates one."""
    with (
        patch(
            "custom_components.discogs.coordinator.discogs_client.Client",
            autospec=True,
        ) as mock_client,
        patch(
            "custom_components.discogs.config_flow.discogs_client.Client",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.identity.return_value = mock_identity
        yield client


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discogs_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration from a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
