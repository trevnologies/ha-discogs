# Discogs for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant sensor integration for Discogs — collection count, wantlist
count, and a random record suggestion from your collection.

This integration was originally part of Home Assistant core
(`homeassistant.components.discogs`), written by [@thibmaek](https://github.com/thibmaek).
It was removed from core and is maintained here as a standalone custom
integration.

## Installation

### HACS
1. Add this repository as a custom repository in HACS (category: Integration)
2. Search for "Discogs" and install
3. Restart Home Assistant

### Manual
Copy `custom_components/discogs` into your `/config/custom_components/`
directory and restart Home Assistant.

## Configuration

```yaml
sensor:
  - platform: discogs
    token: YOUR_DISCOGS_TOKEN
```

Get a personal access token from your
[Discogs developer settings](https://www.discogs.com/settings/developers).

## Optional: dashboard card + auto-refreshing cover art

See [`extras/README.md`](extras/README.md) for the full setup — an
automation, script, shell command, a couple of file sensors, and a
dashboard card that together show a random record with cover art that
refreshes automatically. Not required for the core integration to work;
purely a nice-to-have on top of it.

## License

Apache License 2.0 (inherited from home-assistant/core, the original
source of this integration).
