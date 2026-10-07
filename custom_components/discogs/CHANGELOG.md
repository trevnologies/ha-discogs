# Changelog

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
Initial fork from home-assistant/core's discogs integration (removed
from core). No changes from the original.