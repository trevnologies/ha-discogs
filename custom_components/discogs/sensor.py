"""Discogs collection, wantlist, and random record sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .compat import platform_vol as vol
from .const import (
    CONF_EXCLUDED_SENSORS,
    DEFAULT_NAME,
    DOMAIN,
    SENSOR_COLLECTION_TYPE,
    SENSOR_KEYS,
    SENSOR_RANDOM_RECORD_TYPE,
    SENSOR_WANTLIST_TYPE,
)
from .coordinator import DiscogsConfigEntry, DiscogsCoordinator

ATTR_IDENTITY = "identity"

ICON_RECORD = "mdi:album"
ICON_PLAYER = "mdi:record-player"
UNIT_RECORDS = "records"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_COLLECTION_TYPE,
        translation_key=SENSOR_COLLECTION_TYPE,
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_WANTLIST_TYPE,
        translation_key=SENSOR_WANTLIST_TYPE,
        icon=ICON_RECORD,
        native_unit_of_measurement=UNIT_RECORDS,
    ),
    SensorEntityDescription(
        key=SENSOR_RANDOM_RECORD_TYPE,
        translation_key=SENSOR_RANDOM_RECORD_TYPE,
        icon=ICON_PLAYER,
    ),
)

# Legacy YAML schema, kept only so existing configurations validate and can
# be imported into a config entry on startup.
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import a legacy YAML configuration into a config entry."""
    monitored = config.get(CONF_MONITORED_CONDITIONS, SENSOR_KEYS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_TOKEN: config[CONF_TOKEN],
            CONF_NAME: config.get(CONF_NAME, DEFAULT_NAME),
            CONF_SCAN_INTERVAL: config.get(CONF_SCAN_INTERVAL),
            CONF_EXCLUDED_SENSORS: [k for k in SENSOR_KEYS if k not in monitored],
        },
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        issue = (
            "deprecated_yaml_import_issue_invalid_auth"
            if result.get("reason") == "invalid_auth"
            else "deprecated_yaml_import_issue_cannot_connect"
        )
        async_create_issue(
            hass,
            DOMAIN,
            issue,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=issue,
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": DEFAULT_NAME,
            },
        )
        return

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": DEFAULT_NAME,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DiscogsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Discogs sensors from a config entry."""
    excluded = set(entry.data.get(CONF_EXCLUDED_SENSORS, []))
    async_add_entities(
        DiscogsSensor(
            entry.runtime_data, entry, description, description.key not in excluded
        )
        for description in SENSOR_TYPES
    )


class DiscogsSensor(CoordinatorEntity[DiscogsCoordinator], SensorEntity):
    """A Discogs sensor backed by the shared coordinator."""

    _attr_attribution = "Data provided by Discogs"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DiscogsCoordinator,
        entry: DiscogsConfigEntry,
        description: SensorEntityDescription,
        enabled_default: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.discogs.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(entry.unique_id))},
            manufacturer=DEFAULT_NAME,
            name=entry.title,
        )

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        data = self.coordinator.data
        key = self.entity_description.key
        if key == SENSOR_COLLECTION_TYPE:
            return data.collection_count
        if key == SENSOR_WANTLIST_TYPE:
            return data.wantlist_count
        record = data.random_record
        if not record:
            return None
        artists = record.get("artists") or [{}]
        return f"{artists[0].get('name', 'Unknown artist')} - {record.get('title', '')}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        data = self.coordinator.data
        attrs: dict[str, Any] = {ATTR_IDENTITY: data.user}
        if self.entity_description.key != SENSOR_RANDOM_RECORD_TYPE:
            return attrs
        record = data.random_record
        if not record:
            return attrs

        labels = record.get("labels") or [{}]
        formats = record.get("formats") or [{}]
        fmt = formats[0].get("name", "")
        if descriptions := formats[0].get("descriptions"):
            fmt = f"{fmt} ({descriptions[0]})"
        return {
            "cat_no": labels[0].get("catno"),
            "cover_image": record.get("cover_image"),
            "format": fmt,
            "label": labels[0].get("name"),
            "released": record.get("year"),
            **attrs,
        }
