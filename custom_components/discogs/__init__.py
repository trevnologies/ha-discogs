"""The Discogs integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import DiscogsConfigEntry, DiscogsCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> None:
    """Set up Discogs from a config entry."""
    coordinator = DiscogsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> None:
    """Unload a Discogs config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: DiscogsConfigEntry
) -> None:
    """Reload the entry so a new polling interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
