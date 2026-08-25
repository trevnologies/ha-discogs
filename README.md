# Discogs for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/trevnologies/ha-discogs/actions/workflows/validate.yml/badge.svg)](https://github.com/trevnologies/ha-discogs/actions/workflows/validate.yml)

<p align="center">
  <table>
    <tr>
      <td><img src="images/dashboard-card-example-1.png" width="380" alt="Discogs dashboard card example 1"></td>
      <td><img src="images/dashboard-card-example-2.png" width="380" alt="Discogs dashboard card example 2"></td>
    </tr>
    <tr>
      <td><img src="images/dashboard-card-example-3.png" width="380" alt="Discogs dashboard card example 3"></td>
      <td><img src="images/dashboard-card-example-4.png" width="380" alt="Discogs dashboard card example 4"></td>
    </tr>
  </table>
</p>

Home Assistant sensor integration for Discogs — collection count, wantlist
count, and a random record suggestion from your collection.

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=trevnologies&repository=ha-discogs&category=integration)

1. Click the badge above — opens your HA instance directly to the "add
   custom repository" dialog with this repo pre-filled (requires
   [My Home Assistant](https://www.home-assistant.io/integrations/my/),
   on by default for most setups)
2. Confirm, then find "Discogs" in HACS and install
3. Restart Home Assistant

Or manually:

1. HACS → Integrations → ⋮ (top right) → Custom repositories
2. Repository: `https://github.com/trevnologies/ha-discogs`, Category: Integration
3. Search for "Discogs" and install
4. Restart Home Assistant

### Manual (no HACS)

Copy `custom_components/discogs` into your `/config/custom_components/`
directory and restart Home Assistant.

## Configuration

```yaml
sensor:
  - platform: discogs
    token: !secret discogs_token
    monitored_conditions:
      - collection
      - wantlist
      - random_record
```

`monitored_conditions` is technically optional — it defaults to all
three if omitted. It's shown explicitly here because if you plan to use
the dashboard card in `extras/` (below), all three are required — the
card reads `sensor.discogs_collection`, `sensor.discogs_wantlist`, and
`sensor.discogs_random_record` directly, so trimming this list down will
silently break it.

### Adjusting the refresh interval

The integration polls Discogs every hour by default. To change that,
add `scan_interval` — a built-in option on all legacy YAML-platform
sensors, not something specific to this integration:

```yaml
sensor:
  - platform: discogs
    token: !secret discogs_token
    scan_interval: "00:30:00"   # HH:MM:SS, or a plain number of seconds
    monitored_conditions:
      - collection
      - wantlist
      - random_record
```

If you're using the `extras/` dashboard pipeline, this interval also
paces the whole card-refresh chain — the automation in
`extras/automations.yaml` triggers off `sensor.discogs_random_record`
changing state, so a shorter `scan_interval` means the cover art
refreshes more often too.

## Entities Created

### Sensors
- `sensor.discogs_collection` — total records in your collection
- `sensor.discogs_wantlist` — total records on your wantlist
- `sensor.discogs_random_record` — a random pick from your collection,
  refreshed each poll

## Optional: Dashboard Card + Auto-Refreshing Cover Art

See [`extras/README.md`](extras/README.md) for the full setup — an
automation, script, shell command, a couple of file sensors, and a
dashboard card that together show a random record with cover art that
refreshes automatically. Not required for the core integration to work;
purely a nice-to-have on top of it.

## Troubleshooting

### Integration not found after install
1. Confirm files are in `config/custom_components/discogs/`
2. Check `manifest.json` exists in that folder
3. Restart Home Assistant fully
4. Clear your browser cache

### Sensors show "unknown" or don't update
1. Verify your token is valid — test it directly against the
   [Discogs API](https://www.discogs.com/developers)
2. Check `scan_interval` isn't set unreasonably long
3. Check Settings → System → Logs for API errors

### Dashboard card / cover art not refreshing
This is part of the optional `extras/` pipeline, not the core
integration — see [`extras/README.md`](extras/README.md) for its own
troubleshooting steps.

### Enable debug logging
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.discogs: debug
```
Then restart and check Settings → System → Logs.

## FAQ

**Why is this a custom component instead of built into core?**
It used to be — `homeassistant.components.discogs`, written by
[@thibmaek](https://github.com/thibmaek) — but was removed from core.
This repo picks up where that left off.

**Will this be merged back into core?**
Not something to count on — integrations removed from core are usually
removed for a reason (unmaintained, deprecated API, etc.), though this
fork keeps it working as a standalone option regardless.

**Do I need a paid Discogs account?**
No — a free Discogs account and a personal access token from your
[developer settings](https://www.discogs.com/settings/developers) is
all that's required.

## Attribution

Originally part of Home Assistant core
(`homeassistant.components.discogs`), written by
[@thibmaek](https://github.com/thibmaek). Removed from core and
maintained here as a standalone custom integration.

## Contributing

Issues and pull requests welcome — [GitHub Issues](https://github.com/trevnologies/ha-discogs/issues).

## License

Apache License 2.0 (inherited from home-assistant/core, the original
source of this integration).