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
- Used purely as a cache-busting query param on the cover image URL; the
  actual value doesn't matter, it just needs to exist and be writable.

## 7. Automation

See `automations.yaml`. Fires whenever the random-record sensor's hourly
poll picks a new record, kicking off the cover-sync chain below.

## 8. Script

See `scripts.yaml`. The 4-second delay gives the Discogs sensor's own
update time to land before the shell script reads it; the 2-second delay
gives the shell script time to finish writing the two text files before
the file sensors are force-refreshed.

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
