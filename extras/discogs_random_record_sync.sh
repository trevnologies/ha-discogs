#!/bin/bash
# Downloads the current Discogs random record's cover art and release info,
# writes them to files HA can serve, and bumps a cache-busting timestamp.
#
# Requires /config/.env with:
#   HA_TOKEN=your_long_lived_access_token
#   HA_URL=https://your-ha-instance.example.com

source /config/.env

# File paths
ID_FILE="/config/www/discogs_release_id.txt"
SLUG_FILE="/config/www/discogs_release_slug.txt"
IMAGE_FILE="/config/www/discogs_cover.jpg"
DEBUG_FILE="/config/discogs_debug.json"   # kept outside /www - not web-served

# Step 1: Get Discogs random record sensor JSON
json=$(curl -s -X GET \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  "$HA_URL/api/states/sensor.discogs_random_record")

# Step 2: Save raw data for troubleshooting
echo "$json" > "$DEBUG_FILE"

# Step 3: Extract the cover image URL and record title
cover_url=$(echo "$json" | jq -r '.attributes.cover_image')
record_name=$(echo "$json" | jq -r '.state')

# Step 4: Extract and decode the embedded base64 from the URL.
# Discogs' image CDN URLs embed an S3 object key (base64, prefixed "czM6"
# which decodes to "s3:") that contains the release ID.
base64_part=$(echo "$cover_url" | grep -o 'czM6[^"]*' | tr -d '/')
decoded=$(echo "$base64_part" | base64 -d 2>/dev/null || echo "")
release_id=$(echo "$decoded" | grep -o 'R-[0-9]*' | cut -d'-' -f2)

# Step 5: Slugify the record name for use in URL
slug=$(echo "$record_name" \
  | sed 's/[^a-zA-Z0-9]/-/g' \
  | sed 's/--*/-/g' \
  | sed 's/^-//' \
  | sed 's/-$//')

# Step 6: Write values to disk
echo "$release_id" > "$ID_FILE"
echo "$slug" > "$SLUG_FILE"
curl -s -o "$IMAGE_FILE" "$cover_url"

# Step 7: Update timestamp to trigger cache-busting refresh
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" \
     -H "Content-Type: application/json" \
     -d "{\"state\": \"$(date +%s)\"}" \
     "$HA_URL/api/states/input_text.discogs_image_timestamp"
