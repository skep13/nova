#!/bin/sh
# Ask a CANDIDATE model to be Nova, and score it on the same traits.
#
# eval_models.py measures whether a model can do the JOB. This measures whether
# it can be the CHARACTER, which is a different question and the one that
# decided the last comparison: MiniCPM5-1B scored 8/9 on the tasks and 15/20 on
# the persona, answering "what have you been up to?" by inventing a side
# project it had supposedly been working on.
#
# The hypothesis being tested here is that the persona was simply too long for
# it. Ten of its prohibitions are now enforced in code after the model speaks,
# so the short version is 1145 characters against 5277 and drops nothing that
# was actually load-bearing.
#
#     sh run-persona-eval.sh
#
# The live stack is untouched throughout: the candidate gets the vault
# read-only, writes nothing anywhere, and is removed at the end.
set -eu

cd /opt/orb
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.eval.yml"

# Wait for llama to go quiet. Two models on two cores makes both slow and the
# numbers meaningless, and this box has ~460 MB spare with both up.
echo "waiting for the box to go quiet..."
quiet=0
while [ "$quiet" -lt 3 ]; do
    load=$(docker stats --no-stream --format '{{.CPUPerc}}' orb-llama 2>/dev/null \
           | tr -d '%' | cut -d. -f1)
    load=${load:-0}
    if [ "$load" -lt 40 ]; then
        quiet=$((quiet + 1))
    else
        quiet=0
    fi
    sleep 10
done
echo "  quiet."

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

echo "bringing up the candidate (model + its own router)..."
$COMPOSE up -d llama-eval remote-eval

echo "waiting for it to answer..."
i=0
while [ "$i" -lt 60 ]; do
    if docker exec orb-remote python3 -c \
        'import urllib.request,sys
try: sys.exit(0 if urllib.request.urlopen("http://llama-eval:8080/health",timeout=5).status==200 else 1)
except Exception: sys.exit(1)' >/dev/null 2>&1; then
        echo "  up after ~$((i * 5))s"
        break
    fi
    i=$((i + 1))
    sleep 5
done

echo
echo "=== which persona is it actually running? ==="
docker exec orb-remote-eval python3 -c \
  'import remote_proxy as R, persona
print("  short persona:", R.SHORT_PERSONA)
print("  chars:", len(persona.PERSONA_SHORT if R.SHORT_PERSONA else persona.PERSONA))
print("  writes:", R.RESEARCH_WRITES)' 2>&1 | tail -4

echo
echo "=== the traits ==="
docker cp test_personality.py orb-remote:/app/test_personality.py >/dev/null
docker exec -e NOVA_TEST_ROUTER=http://remote-eval:5003/ask \
    orb-remote python3 /app/test_personality.py --quick 2>&1 || true

echo
echo "=== removing the candidate ==="
$COMPOSE stop llama-eval remote-eval >/dev/null 2>&1 || true
$COMPOSE rm -f llama-eval remote-eval >/dev/null 2>&1 || true
docker ps -a --format '{{.Names}}' | grep -q eval \
    && echo "WARNING: a candidate container survived" \
    || echo "gone; live stack untouched"
free -m | head -2 | tail -1
