# Changelog

## 1.1.0

### Added
- UI setup via Settings → Devices & services → Add integration → Discogs,
  ported from Home Assistant core's new Discogs config flow (core 2026.10).
  The form asks for your API token and a name; keeping the default name
  "Discogs" gives the same entity IDs as before
  (`sensor.discogs_collection`, `sensor.discogs_wantlist`,
  `sensor.discogs_random_record`).
- Polling interval option (Configure on the integration, 5–1440 minutes,
  default 60), replacing YAML `scan_interval`.
- Re-authentication: if Discogs rejects the token, Home Assistant prompts
  for a new one instead of the sensors silently going stale.
- The three sensors are grouped under a Discogs service device.
- Test suite (`tests/`) and a `Tests` workflow, run against Home Assistant
  2025.1, 2026.9 and the 2026.10 beta for this release.
- Weekly `upstream-sync-check` workflow that opens/updates an
  `upstream-sync` issue when core's `discogs` integration changes. It
  stores its position in the issue, so it never pushes to `main`.

### Changed
- Existing `sensor: - platform: discogs` YAML is imported into a config
  entry automatically on the first restart after updating. `name`,
  `scan_interval` and `monitored_conditions` carry over (sensors left out of
  `monitored_conditions` are created disabled), and entity IDs stay the
  same. A repair notice then asks you to remove the YAML. YAML setup is
  deprecated and will be removed in a future release.
- All sensors now share one Discogs fetch per poll through a
  DataUpdateCoordinator, replacing 1.0.2's timestamp guard. Throttled or
  malformed responses still keep the last known values.
- `homeassistant.update_entity` on any Discogs sensor (as used by the
  `extras/` refresh script) refreshes all three and picks a new random
  record in one fetch.
- Schemas are built with whichever validation library the running Home
  Assistant uses (voluptuous, or probatio from 2026.9/2026.10), so the
  integration keeps working as core finishes dropping voluptuous.
- Minimum Home Assistant version is now 2025.1.0.

### Fixed
- Random record attributes no longer raise if a release has no format
  description, label, or artist.

## 1.0.3

### Fixed
- Hassfest validation failing on the `discogs-client` requirement.
  Home Assistant core depends on the same package, and hassfest now
  rejects exact (`==`) pins on core dependencies. The requirement is
  now `discogs-client>=2.3.0`, so the integration follows whatever
  version Home Assistant ships instead of conflicting with it when
  core updates the library.

### Changed
- `documentation` and `issue_tracker` links in `manifest.json` now
  point to `trevnologies/ha-discogs` instead of the old
  `ha-discogs-addon` repo name.

## 1.0.2

### Fixed
- Fixed a race condition where all three sensor entities (Collection,
  Wantlist, Random Record) independently re-fetched identity and
  collection data from Discogs on every scan cycle, firing three
  redundant near-simultaneous API calls. The third call was
  consistently getting throttled by Discogs, causing an hourly
  "Update for sensor.discogs_random_record fails" error.
- The fetch is now gated behind a shared timestamp so only one
  entity's update() per scan cycle hits the Discogs API.
- Bad or malformed API responses (JSONDecodeError, RequestException)
  now log a warning and keep the last known-good data instead of
  raising an error.

## 1.0.1
Initial fork from home-assistant/core's discogs integration. No changes
from the original.