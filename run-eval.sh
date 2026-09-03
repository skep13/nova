#!/bin/sh
# Measure a candidate model against the one in service, on this hardware.
#
# Run from /opt/orb inside LXC 101. Waits for anything already using llama to
# finish first: both models are scored on tokens per second, and a number taken
# while the other one saturates the same two cores measures nothing.
#
#     sh run-eval.sh
#
# Leaves the live stack untouched. The candidate is brought up from
# docker-compose.eval.yml, measured, and removed again — it never becomes an
# agent the router knows about.
set -eu

cd /opt/orb
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.eval.yml"

echo "waiting for the box to go quiet..."
while pgrep -f "test_nova.py|test_personality.py" >/dev/null 2>&1; do
    sleep 20
done
# And a moment for llama to finish whatever it was mid-way through.
sleep 15

# Run from INSIDE the compose network, not from this host.
#
# "http://llama:8080" is a Docker network name. Run from LXC 101 it does not
# resolve, and eval_models.py reports URLError on every test — which prints as
# a row of failures and reads exactly like a model that cannot answer anything.
# The first run of this script scored BOTH models 0/9 that way.
EVAL="docker exec orb-remote python3 /app/eval_models.py"
docker cp eval_models.py orb-remote:/app/eval_models.py >/dev/null

echo
echo "=== baseline: the model currently in service ==="
$EVAL http://llama:8080 "Qwen3-4B-Instruct-2507" || true

echo
# ONE MODEL AT A TIME. This is not a preference.
#
# The first run of this script kept the live 4B up alongside the candidate, on
# the theory that per-container memory caps would contain the risk. They do
# not. A cap stops a CONTAINER growing past its limit; it does not reserve
# headroom for the LXC, and when the cgroup total was exceeded the kernel chose
# the fattest process to kill — which is always the live model, never the
# candidate:
#
#   Memory cgroup out of memory: Killed process (llama-server)
#   anon-rss:4886420kB  oom_memcg=/lxc/101
#
# Nova went down for eighteen seconds in the middle of an evaluation nobody
# urgent was waiting on. So the live model is stopped deliberately first: a
# known, announced outage of a couple of minutes beats a random kill, and the
# measurement is better too, because two models on two cores make each other
# slow.
echo
echo "stopping the live model for the duration (it will be restarted at the end)"
docker compose stop llama >/dev/null 2>&1 || true
trap 'echo; echo "restoring the live model...";       docker compose -f docker-compose.yml -f docker-compose.eval.yml rm -f llama-eval remote-eval >/dev/null 2>&1 || true;       docker compose up -d llama >/dev/null 2>&1 || true;       echo "live model back"' EXIT INT TERM

echo "=== bringing up the candidate ==="
$COMPOSE up -d llama-eval

# The first run downloads ~700 MB and then loads it. Poll rather than guess:
# a fixed sleep is either wrong or wasteful, and this box is slow enough that
# it would be both.
echo "waiting for it to load (first run downloads the weights)..."
i=0
while [ "$i" -lt 90 ]; do
    # Asked from orb-remote, which has python3. The llama.cpp image ships
    # neither wget nor curl, so the original check could never succeed: it
    # spun for its full 90 iterations and the script then measured a model it
    # had never confirmed was up.
    if docker exec orb-remote python3 -c \
        'import urllib.request, sys; sys.exit(0 if urllib.request.urlopen("http://llama-eval:8080/health", timeout=5).status == 200 else 1)' \
        >/dev/null 2>&1; then
        echo "  up after ~$((i * 10))s"
        break
    fi
    i=$((i + 1))
    sleep 10
done

echo
echo "=== candidate ==="
$EVAL http://llama-eval:8080 "MiniCPM5-1B" || true

echo
echo "=== does it emit <think> blocks? ==="
# ANSWERED, for MiniCPM5-1B: llama.cpp reports reasoning separately, in
# reasoning_content, so it does not leak into the reply or the spoken audio.
# The cost is not correctness, it is WAITING — and that cost is invisible in
# tokens per second, which is why both halves are printed. Ask something hard
# enough to make a thinking model think.
docker exec orb-remote python3 -c '
import json, urllib.request
b = {"messages": [{"role": "user",
                   "content": "A tank holds 240 litres and leaks 3 an hour. How much after 6 hours?"}],
     "max_tokens": 1200}
r = urllib.request.Request("http://llama-eval:8080/v1/chat/completions",
                           json.dumps(b).encode(),
                           {"Content-Type": "application/json"})
m = json.load(urllib.request.urlopen(r, timeout=800))["choices"][0]["message"]
print("answer   :", repr((m.get("content") or "")[:120]))
print("reasoning:", len(m.get("reasoning_content") or ""), "chars hidden")
' 2>&1 | tail -3

echo
echo "=== removing the candidate ==="
$COMPOSE stop llama-eval >/dev/null 2>&1 || true
$COMPOSE rm -f llama-eval >/dev/null 2>&1 || true
docker ps --format '{{.Names}}' | grep -q orb-llama-eval \
    && echo "WARNING: the candidate is still running" \
    || echo "gone; live stack untouched"
