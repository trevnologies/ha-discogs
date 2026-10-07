"""Data update coordinator for the Discogs integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from json import JSONDecodeError
import random
from typing import Any

import discogs_client
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)

type DiscogsConfigEntry = ConfigEntry[DiscogsCoordinator]

# Errors that mean "Discogs returned something unusable this time" rather
# than "the token is bad". Seen in practice as throttled/empty responses.
TRANSIENT_ERRORS = (
    discogs_client.exceptions.HTTPError,
    JSONDecodeError,
    RequestException,
)


@dataclass
class DiscogsData:
    """Snapshot of one Discogs poll, shared by every sensor of an entry."""

    user: str
    collection_count: int
    wantlist_count: int
    random_record: dict[str, Any] | None = field(default=None)


def is_auth_error(err: Exception) -> bool:
    """Return True if a Discogs error means the token was rejected."""
    return (
        isinstance(err, discogs_client.exceptions.HTTPError)
        and getattr(err, "status_code", None) == 401
    )


class DiscogsCoordinator(DataUpdateCoordinator[DiscogsData]):
    """Fetch Discogs data once per poll for all sensors of a config entry.

    The legacy YAML sensors each re-fetched identity and collection data on
    every scan, firing three near-simultaneous API calls that Discogs
    throttled. A single coordinator replaces both that and the 1.0.2
    timestamp guard: one fetch per poll, shared by all sensors.
    """

    config_entry: DiscogsConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DiscogsConfigEntry) -> None:
        """Initialize the coordinator."""
        minutes = entry.options.get(CONF_SCAN_INTERVAL_MINUTES)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=(
                timedelta(minutes=minutes) if minutes else DEFAULT_SCAN_INTERVAL
            ),
        )
        self.client = discogs_client.Client(
            SERVER_SOFTWARE, user_token=entry.data[CONF_TOKEN]
        )

    async def _async_update_data(self) -> DiscogsData:
        """Fetch the latest data from Discogs."""
        return await self.hass.async_add_executor_job(self._fetch)

    def _fetch(self) -> DiscogsData:
        """Fetch counts and a new random record (runs in the executor)."""
        previous = self.data
        try:
            identity = self.client.identity()
            folders = identity.collection_folders
            data = DiscogsData(
                user=identity.name,
                collection_count=identity.num_collection,
                wantlist_count=identity.num_wantlist,
            )
        except TRANSIENT_ERRORS as err:
            if is_auth_error(err):
                raise ConfigEntryAuthFailed("Discogs rejected the API token") from err
            if previous is None:
                raise UpdateFailed(f"Error communicating with Discogs: {err}") from err
            # Same behavior as 1.0.2: a bad response keeps the last
            # known-good values instead of blanking the sensors.
            LOGGER.warning(
                "Failed to refresh Discogs data, keeping last known values: %s", err
            )
            return previous

        data.random_record = self._pick_random_record(
            folders, previous.random_record if previous else None
        )
        return data

    @staticmethod
    def _pick_random_record(
        folders: Any, fallback: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Pick a random release from the 'All' collection folder."""
        try:
            # Index 0 in the folders is the 'All' folder
            collection = folders[0]
            if collection.count <= 0:
                return None
            index = random.randrange(collection.count)
            return dict(collection.releases[index].release.data)
        except TRANSIENT_ERRORS as err:
            LOGGER.warning(
                "Failed to fetch a random record from Discogs, keeping previous value: %s",
                err,
            )
            return fallback
