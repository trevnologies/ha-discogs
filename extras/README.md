# extras/README.md

# Extras — Discogs Dashboard Pipeline

The `custom_components/discogs/` integration only gets you three sensors
(`sensor.discogs_collection`, `sensor.discogs_wantlist`,
`sensor.discogs_random_record`). Everything in this folder is the extra
plumbing that turns those sensors into the auto-refreshing dashboard card
with cover art. **None of this is installed by HACS** — HACS only manages
the `custom_components/discogs/` folder. Everything below is a manual,
one-time setup on top of it.

Setup order matters — later steps depend on entities/helpers created in
earlier ones.

## 1. Discogs token

Get a personal access token from your
[Discogs developer settings](https://www.discogs.com/settings/developers),
then add it to `secrets.yaml`:

```yaml
# secrets.yaml
discogs_token: your_token_here
```

## 2. Discogs sensor platform

Add to `configuration.yaml` (also in `configuration-snippet.yaml` in
this folder):

```yaml
sensor:
  - platform: discogs
    token: !secret discogs_token
    monitored_conditions:
      - collection
      - wantlist
      - random_record
```

Restart Home Assistant. Confirm `sensor.discogs_collection`,
`sensor.discogs_wantlist`, and `sensor.discogs_random_record` all show up
with real values before continuing.

Want a different refresh cadence than the hourly default? See the
"Adjusting the refresh interval" section in the top-level README —
`scan_interval` also controls how often this whole extras pipeline
fires, since everything below is triggered off `sensor.discogs_random_record`
changing state.

## 3. Cover-sync script

Copy `discogs_random_record_sync.sh` to `/config/scripts/` and make it
executable:

```bash
mkdir -p /config/scripts
cp discogs_random_record_sync.sh /config/scripts/
chmod +x /config/scripts/discogs_random_record_sync.sh
```

Requires `jq` on the HA host (`apk add jq` via the SSH addon on HAOS if
not already present).

Create `/config/.env` from the template (this file is gitignored — never
commit it):

```bash
cp .env.example /config/.env
```

Edit `/config/.env`:

```bash
HA_TOKEN=your_long_lived_access_token
HA_URL=https://your-ha-instance
```

Generate the long-lived token from your HA profile page
(Settings → your profile → Security → Long-Lived Access Tokens).

## 4. Shell command

Add to `configuration.yaml` (also in `configuration-snippet.yaml`):

```yaml
shell_command:
  sync_discogs_cover: bash /config/scripts/discogs_random_record_sync.sh
```

## 5. File sensors (UI only — cannot be done in YAML)

These use HA's built-in **Local File** integration, which is config-entry
based and has no YAML schema:

1. Settings → Devices & Services → Add Integration → search "Local File"
2. File path: `/config/www/discogs_release_id.txt` → creates
   `sensor.discogs_release_id`
3. Repeat: Add Integration → Local File →
   `/config/www/discogs_release_slug.txt` → creates
   `sensor.discogs_release_slug`
4. Leave the value template at its default (`{{ value }}`) on both

## 6. Helper

Settings → Devices & Services → Helpers → Add Helper → **Text**:
- Entity ID: `input_text.discogs_image_timestamp`
- Name: `Discogs Image Timestamp`
- Icon: `mdi:clock-digital`
- Min/max length: defaults are fine (0 / 100)
- Used purely as a cache-busting query param on the cover image URL; the
  actual value doesn't matter, it just needs to exist and be writable.

## 7. Automations

See `automations.yaml` — there are two:

- **"Discogs - Refresh on Random Record Change"** — fires whenever the
  random-record sensor's hourly poll picks a new record, kicking off
  the cover-sync chain below. **Important:** this one calls
  `script.sync_discogs_cover_only`, not
  `script.refresh_discogs_record_and_cover` — see step 8 for why the
  distinction matters. Calling the wrong script here creates a
  self-sustaining feedback loop that fires dozens of Discogs API calls
  in under a minute, every time the sensor's hourly poll runs.
- **"Discogs - Refresh on Home Assistant Start"** — fires once, only
  on HA startup, forcing a fresh pick so the dashboard doesn't show
  stale pre-restart data. This one *is* safe to point at
  `script.refresh_discogs_record_and_cover` (the force-a-new-pick
  script) — the `homeassistant.start` event only fires once per boot,
  so it can't re-trigger itself. The pick it forces cascades through
  the automation above exactly once, then stops.

Optional cosmetic step: both automations use a custom icon,
`mdi:record-player`, instead of HA's default automation icon. This is
a UI-only setting (icon overrides aren't part of automation YAML) —
set via each automation's ⋮ menu → Icon, if you want to match.

## 8. Scripts

See `scripts.yaml` — there are two, and the split is deliberate:

- **`refresh_discogs_record_and_cover`** — forces a brand-new random
  pick, then syncs cover art. Used by the dashboard card's refresh
  button (step 9), where forcing a new pick is exactly what you want.
- **`sync_discogs_cover_only`** — syncs cover art for whatever record
  is *already* current, without forcing a new pick. Used by the
  automation in step 7.

Why two scripts: the automation triggers on *any* state change of
`sensor.discogs_random_record`. If it called the force-a-new-pick
script, that new pick would itself be a state change, re-triggering the
same automation, forcing another pick, forever — an infinite loop.
Routing the automation through the non-forcing script breaks that
cycle: it has nothing left to react to after running once.

In both scripts, the 4-second delay (where present) gives the Discogs
sensor's own update time to land before the shell script reads it; the
2-second delay gives the shell script time to finish writing the two
text files before the file sensors are force-refreshed.

## 9. Dashboard card

Requires the [card-mod](https://github.com/thomasloven/lovelace-card-mod)
and [button-card](https://github.com/custom-cards/button-card) custom
cards (install both via HACS → Frontend first).

See `dashboard-card.yaml` — paste its contents into a new card via
Edit Dashboard → Add Card → Manual.

---

## Verifying it all works

1. Call `script.refresh_discogs_record_and_cover` manually (Developer
   Tools → Actions, or the refresh icon on the card itself)
2. `sensor.discogs_random_record` should update within a couple seconds
3. `/config/www/discogs_cover.jpg` and the two `.txt` files should have
   a fresh modified timestamp
4. The dashboard card's background image and "Featuring" line should
   update within ~6 seconds of triggering the script