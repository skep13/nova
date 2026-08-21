#!/bin/sh
# Nightly snapshot of the parts of Orb that exist nowhere else.
#
# The git repo deliberately excludes all of this: mem/ is personal, logs/ is a
# record of what was asked, keys/ are secrets. That makes them exactly the
# files with no second copy anywhere — a container rebuild or a disk fault
# loses them silently, and nobody notices until they are wanted.
#
# logs/ matters more than it looks: it is now the recall corpus, so it IS the
# accumulated knowledge the device has picked up from the hosted models.
set -eu

DEST=/var/backups/orb
KEEP_DAYS=30
CTID=101
STAMP=$(date +%Y-%m-%d)

mkdir -p "$DEST"
chmod 700 "$DEST"          # contains API keys

# Stream the tar out of the container rather than writing inside it: the LXC
# disk is at 89% and has no room for a copy of its own data.
pct exec "$CTID" -- tar czf - -C /opt/orb \
    mem keys logs docker-compose.yml nginx.conf index.html remote_proxy.py \
    > "$DEST/orb-$STAMP.tar.gz.part"

mv "$DEST/orb-$STAMP.tar.gz.part" "$DEST/orb-$STAMP.tar.gz"
chmod 600 "$DEST/orb-$STAMP.tar.gz"

# Verify it is readable before trusting it. An unverified backup is a guess.
gzip -t "$DEST/orb-$STAMP.tar.gz"

find "$DEST" -name 'orb-*.tar.gz' -mtime +"$KEEP_DAYS" -delete
find "$DEST" -name '*.part' -mtime +1 -delete    # tidy interrupted runs

printf '%s ok %s (%s)\n' "$(date -Is)" "orb-$STAMP.tar.gz" \
    "$(du -h "$DEST/orb-$STAMP.tar.gz" | cut -f1)" >> "$DEST/backup.log"
