#!/bin/sh
# Nightly snapshot of the parts of Nova that exist nowhere else.
#
# The git repo deliberately excludes all of this: mem/ is personal, logs/ is a
# record of what was asked, keys/ are secrets. That makes them exactly the
# files with no second copy anywhere — a container rebuild or a disk fault
# loses them silently, and nobody notices until they are wanted.
#
# logs/ matters more than it looks: it is the recall corpus, so it IS the
# accumulated knowledge the device has picked up from the hosted models.
#
# ---------------------------------------------------------------------------
# THIS SCRIPT SILENTLY DID NOTHING FOR A WEEK. Read before editing.
#
# `pct` lives in /usr/sbin. A root USER crontab (crontab -e) runs with
# PATH=/usr/bin:/bin — it does not inherit the PATH set in /etc/crontab — so
# pct was not found. The shell had already created the .part file by opening
# the redirect, then the command failed and `set -e` aborted, leaving a
# 0-byte file and no error anywhere, because the crontab line ended in
# `>/dev/null 2>&1`.
#
# The last good backup was 22 August, taken by hand. Every scheduled run after
# it failed, through the entire period in which the 343-note vault was built.
#
# Three things now prevent a repeat:
#   1. PATH is set explicitly here and pct is called by absolute path.
#   2. The archive is VERIFIED to contain notes, not merely to be valid gzip.
#      An empty tar is perfectly valid gzip, which is exactly how you end up
#      trusting a backup of nothing.
#   3. Success and failure are both reported into the container, where
#      /health reads the age and the page shows a fault chip if it goes stale.
#      A backup nobody checks is a backup that is not happening.
# ---------------------------------------------------------------------------
set -eu

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
PCT=/usr/sbin/pct

DEST=/var/backups/nova
KEEP_DAYS=30
CTID=101
STAMP=$(date +%Y-%m-%d)
ARCHIVE="$DEST/nova-$STAMP.tar.gz"
PART="$ARCHIVE.part"

# Optional off-box copy. The backups otherwise sit on the same physical disk
# (sda) as the thing they back up, so a drive failure takes both. Set this to
# an scp target reachable over Tailscale — e.g. user@fedora-laptop:/backups —
# and add a key. Left empty it is skipped without complaint, because a laptop
# that is asleep must not fail the backup.
OFFBOX="${NOVA_BACKUP_OFFBOX:-}"

note() { printf '%s %s\n' "$(date -Is)" "$*" >> "$DEST/backup.log"; }

# Report status back INTO the container, so /health can see it and the page can
# show a fault chip when this stops running. Best effort: a reporting failure
# must never fail the backup itself.
report() {
    "$PCT" exec "$CTID" -- sh -c \
        "mkdir -p /opt/orb/logs && printf '%s' '$1' > /opt/orb/logs/backup-status.json" \
        >/dev/null 2>&1 || true
}

fail() {
    note "FAILED $*"
    report "{\"ok\":false,\"at\":\"$(date -Is)\",\"error\":\"$*\"}"
    exit 1
}

# Not $LINENO: /bin/sh here is dash, which does not set it, so the message read
# "aborted at line " with nothing after it — a diagnostic that says less than
# silence would.
trap 'fail "aborted before completion"' EXIT INT TERM

mkdir -p "$DEST"
chmod 700 "$DEST"          # contains API keys

[ -x "$PCT" ] || fail "pct not found at $PCT"

# Stream the tar out of the container rather than writing inside it: the LXC
# disk has no room for a copy of its own data.
#
# --warning=no-file-changed: mem/ is live and Obsidian may sync mid-run. tar
# exits 1 on "file changed as we read it", which under set -e would abort a
# backup that is in fact fine.
"$PCT" exec "$CTID" -- tar czf - --warning=no-file-changed -C /opt/orb \
    mem keys logs docker-compose.yml nginx.conf index.html remote_proxy.py \
    > "$PART" || fail "tar/pct returned $?"

[ -s "$PART" ] || fail "archive is empty"
gzip -t "$PART" || fail "archive is not valid gzip"

# Valid gzip is not the same as useful. An empty tar passes gzip -t, so count
# what is actually in there and refuse to keep an archive with no notes.
NOTES=$(tar tzf "$PART" | grep -c '^mem/.*\.md$' || true)
[ "$NOTES" -ge 50 ] || fail "only $NOTES notes in the archive — expected the vault"

# Then against the LIVE vault, not just a floor.
#
# A fixed floor of 50 answers "did the archive come back empty" and nothing
# else: an archive holding 100 notes out of 1400 sails past it, reports "ok",
# and is the backup you discover is useless on the day you need it. The vault
# only ever grows, so anything meaningfully short of the real count is a
# partial capture and must not be kept.
#
# 95%, not 100%: mem/ is live and Obsidian can sync mid-run, so a handful of
# files appearing or vanishing between the count and the tar is normal. A
# fifth of the vault going missing is not.
LIVE=$("$PCT" exec "$CTID" -- sh -c 'ls /opt/orb/mem/*.md 2>/dev/null | wc -l' 2>/dev/null || echo 0)
if [ "$LIVE" -gt 0 ]; then
    MIN=$(( LIVE * 95 / 100 ))
    [ "$NOTES" -ge "$MIN" ] || fail "archive has $NOTES notes but the vault has $LIVE — partial capture"
fi

mv "$PART" "$ARCHIVE"
chmod 600 "$ARCHIVE"

SIZE=$(du -h "$ARCHIVE" | cut -f1)

if [ -n "$OFFBOX" ]; then
    if scp -q -o ConnectTimeout=20 -o BatchMode=yes "$ARCHIVE" "$OFFBOX/" 2>/dev/null; then
        note "offbox ok $OFFBOX"
    else
        # Deliberately not fatal: the far end being asleep is normal, and a
        # local backup that exists beats a failed run that does not.
        note "offbox UNREACHABLE $OFFBOX (local copy kept)"
    fi
fi

find "$DEST" -name 'nova-*.tar.gz' -mtime +"$KEEP_DAYS" -delete
find "$DEST" -name 'orb-*.tar.gz'  -mtime +"$KEEP_DAYS" -delete   # pre-rename
find "$DEST" -name '*.part' -mtime +1 -delete                     # interrupted runs

note "ok nova-$STAMP.tar.gz ($SIZE, $NOTES notes)"
report "{\"ok\":true,\"at\":\"$(date -Is)\",\"file\":\"nova-$STAMP.tar.gz\",\"size\":\"$SIZE\",\"notes\":$NOTES}"

trap - EXIT
