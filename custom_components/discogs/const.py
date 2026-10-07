"""Constants for the Discogs integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "discogs"
PLATFORMS: Final = [Platform.SENSOR]

DEFAULT_NAME: Final = "Discogs"

# Options
CONF_SCAN_INTERVAL_MINUTES: Final = "scan_interval_minutes"
DEFAULT_SCAN_INTERVAL: Final = timedelta(hours=1)
MIN_SCAN_INTERVAL_MINUTES: Final = 5
MAX_SCAN_INTERVAL_MINUTES: Final = 1440

# Config entry data key set only by the YAML import: sensors that were
# left out of the old `monitored_conditions` list. They are still created,
# but registered disabled, so the import doesn't add entities the user had
# deliberately excluded.
CONF_EXCLUDED_SENSORS: Final = "excluded_sensors"

SENSOR_COLLECTION_TYPE: Final = "collection"
SENSOR_WANTLIST_TYPE: Final = "wantlist"
SENSOR_RANDOM_RECORD_TYPE: Final = "random_record"
SENSOR_KEYS: Final = [
    SENSOR_COLLECTION_TYPE,
    SENSOR_WANTLIST_TYPE,
    SENSOR_RANDOM_RECORD_TYPE,
]
