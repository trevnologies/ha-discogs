"""The Discogs integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import DiscogsConfigEntry, DiscogsCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> bool:
    """Set up Discogs from a config entry."""
    coordinator = DiscogsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> bool:
    """Unload a Discogs config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: DiscogsConfigEntry
) -> None:
    """Reload the entry so a new polling interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
