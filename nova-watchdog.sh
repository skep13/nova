#!/bin/sh
# Restart the Telegram bridge if it has stopped proving it is alive.
#
# watch_health, inside the bridge, reports on the SERVICES: llama, the vault,
# the backup age. Nothing reported on the bridge itself, and that is the one
# failure that silences every other alarm — a wedged poll loop keeps the
# process running and the container "up", so `restart: unless-stopped` never
# fires, watch_health never runs to notice anything, and the first symptom is a
# message that is simply never answered.
#
# So the bridge stamps a heartbeat into its state file on every reminder sweep
# (every 15s), and this checks the stamp from OUTSIDE the container. A monitor
# that lives inside the thing it monitors is not a monitor.
#
# Recovery rather than alerting, deliberately: the only process that can send
# him a message is the one that is broken, so there is nobody to tell. Restart
# it and write to the log; if it is still dead next minute, restart it again.
set -eu

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
STATE=${BRIDGE_STATE:-/opt/orb/logs/bridge-state.json}
LOG=${WATCHDOG_LOG:-/opt/orb/logs/watchdog.log}
CONTAINER=${BRIDGE_CONTAINER:-nova-bridge}

# Three missed sweeps, not one. The box has two cores and llama saturates both;
# a sweep that lands late under load is normal and must not cost a restart.
STALE_AFTER=${STALE_AFTER:-120}

say() { printf '%s %s\n' "$(date -Is)" "$*" >>"$LOG"; }

[ -f "$STATE" ] || { say "no state file at $STATE; nothing to check"; exit 0; }

beat=$(sed -n 's/.*"heartbeat"[[:space:]]*:[[:space:]]*\([0-9]\{1,\}\).*/\1/p' "$STATE")

# No heartbeat key at all means a bridge older than this watchdog, or one that
# has not completed its first sweep. Neither is a fault worth restarting for.
[ -n "${beat:-}" ] || { say "no heartbeat recorded yet; leaving it alone"; exit 0; }

age=$(( $(date +%s) - beat ))
[ "$age" -le "$STALE_AFTER" ] && exit 0

say "heartbeat is ${age}s old (limit ${STALE_AFTER}s) - restarting $CONTAINER"
if docker restart "$CONTAINER" >/dev/null 2>&1; then
    say "restarted $CONTAINER"
else
    say "FAILED to restart $CONTAINER"
    exit 1
fi
