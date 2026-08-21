#!/bin/sh
# IBM Plex Mono, self-hosted. Fetched rather than committed: 45 KB of binary in
# git for something reproducible in one command is a poor trade, and the page
# degrades to ui-monospace if these are ever missing.
set -eu
DEST=${1:-./fonts}
mkdir -p "$DEST"
for w in 400 500 600; do
  curl -sSL -m 60 -o "$DEST/plex-mono-$w.woff2" \
    "https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-$w-normal.woff2"
  printf '  %s  %s bytes\n' "plex-mono-$w.woff2" "$(stat -c%s "$DEST/plex-mono-$w.woff2")"
done
