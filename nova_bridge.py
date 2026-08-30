"""Nova over Telegram: a way to talk to her, and a way for her to speak first.

Two things the web page cannot do. It cannot be reached when it is not open,
and it cannot get your attention — the backup died on 22 August and stayed dead
for seven days precisely because nothing was able to tell anyone. A bot message
is a push notification on a phone, so one mechanism covers both directions.

WHY TELEGRAM, and not the WhatsApp that was asked for.

Telegram supports long polling: this process dials OUT and holds the connection
open. Nothing listens on a port, nothing is published, and Tailscale Funnel
stays off — which matters here more than usual, because the WebDAV vault is
served without authentication by request, and a public endpoint on this box
would expose it. WhatsApp's official Cloud API requires an inbound HTTPS
webhook, so it cannot be done without that exposure; the unofficial libraries
avoid the webhook but attach to a personal number in violation of the terms,
and the number that gets banned is the user's own.

WHAT THIS IS NOT. iOS does not let any application read another application's
notifications — there is no equivalent of Android's notification listener, and
no entitlement that grants it. Nova cannot announce an incoming WhatsApp or
email that arrives on the phone. She can only tell you things she worked out
herself, which is what the alerting half of this file is for.

SECURITY. A bot's username is discoverable and anyone may message it, so the
allowlist is default-deny and holds numeric chat IDs. Without it, a stranger
gets an assistant with the whole vault attached — which is a personal note
archive, not a public encyclopedia. An unknown sender is refused and told their
own chat ID, which is not a secret and is the only practical way to enrol.
"""
import asyncio
import json
import os
import pathlib
import time

import aiohttp

ASK_URL = os.environ.get("NOVA_ASK_URL", "http://remote:5003/ask")
HEALTH_URL = os.environ.get("NOVA_HEALTH_URL", "http://remote:5003/health")
KEY_FILE = pathlib.Path(os.environ.get("TG_KEY", "/run/keys/telegram.key"))
STATE_FILE = pathlib.Path(os.environ.get("BRIDGE_STATE", "/logs/bridge-state.json"))

# Numeric chat IDs, comma separated. Empty means nobody, deliberately: an
# accidentally empty variable must lock the bot down rather than open it up.
ALLOW = {c.strip() for c in os.environ.get("NOVA_TG_ALLOW", "").split(",") if c.strip()}

HEALTH_EVERY = int(os.environ.get("NOVA_HEALTH_EVERY", "300"))
MAX_REPLY = 3800          # Telegram's limit is 4096; leave room for a prefix
PER_MIN = int(os.environ.get("NOVA_TG_PER_MIN", "12"))

_seen = {}                # chat id -> [timestamps], for the rate limit
_history = {}             # chat id -> [(role, content), ...]
HISTORY_TURNS = 6


def token():
    """The bot token, read at use rather than held in a module global.

    Same handling as the model keys: mounted read-only, never logged, never
    included in an error message. A token in a traceback is a token in a log
    file, and this one grants the ability to impersonate Nova.
    """
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def rate_ok(chat):
    """A crude per-chat ceiling.

    Not protection against an attacker — the allowlist is that — but against a
    loop. A retry storm or a mis-wired automation talking to a two-core laptop
    would otherwise queue model calls until nothing else could run.
    """
    now = time.time()
    hits = [t for t in _seen.get(chat, []) if now - t < 60]
    hits.append(now)
    _seen[chat] = hits
    return len(hits) <= PER_MIN


def remember(chat, role, content):
    h = _history.setdefault(chat, [])
    h.append((role, content))
    del h[:-HISTORY_TURNS * 2]


async def send(session, chat, text):
    """One message out. Long replies are split rather than truncated."""
    tok = token()
    if not tok:
        return
    text = text.strip() or "(no answer)"
    while text:
        chunk, text = text[:MAX_REPLY], text[MAX_REPLY:]
        try:
            async with session.post(
                    f"https://api.telegram.org/bot{tok}/sendMessage",
                    json={"chat_id": chat, "text": chunk,
                          "disable_web_page_preview": True}) as r:
                await r.read()
        except Exception:
            return          # a failed send is not worth killing the loop over


async def health_line(session):
    """One sentence on how Nova is, assembled here rather than by the model.

    Status is a question with a correct answer, and a 3B asked to summarise a
    health blob will occasionally invent a reassuring one. The page settled
    this the same way.
    """
    try:
        async with session.get(HEALTH_URL) as r:
            h = await r.json()
    except Exception as exc:
        return "down", f"I cannot reach my own health endpoint ({type(exc).__name__})."

    failing = h.get("failing") or []
    backup = (h.get("checks") or {}).get("backup") or {}
    age = backup.get("age_hours")
    parts = []
    if failing:
        parts.append("Not well: " + ", ".join(failing) + " failing.")
    else:
        parts.append("All services responding.")
    if isinstance(age, (int, float)):
        parts.append(f"Last backup {age:.0f} hours ago"
                     + (f", {backup.get('notes')} notes." if backup.get("notes") else "."))
    return (h.get("state") or "unknown"), " ".join(parts)


async def watch_health(session):
    """Speak up when something changes, and only then.

    Alerting on STATE rather than on a transition is how a monitor becomes
    noise: a backup that has been broken since Tuesday would message every five
    minutes until it was fixed or muted, and a muted alert is no alert. So the
    last state is persisted, and a message is sent when it differs — including
    the recovery, because knowing it came back matters as much as knowing it
    went.
    """
    state = load_state()
    while True:
        try:
            now, line = await health_line(session)
            if now != state.get("health"):
                was = state.get("health")
                if was is not None:      # never alert on first boot
                    for chat in sorted(ALLOW):
                        await send(session, chat,
                                   ("Recovered. " if now == "ok" else "Something is wrong. ")
                                   + line)
                state["health"] = now
                save_state(state)
        except Exception:
            pass
        await asyncio.sleep(HEALTH_EVERY)


async def answer(session, chat, text):
    low = text.strip().lower()

    # Deterministic commands, answered without the model for the same reason
    # the page does it: these have correct answers, and a small model asked to
    # report on itself will produce a plausible one instead.
    if low in ("status", "health", "what's wrong", "whats wrong", "how are you"):
        _, line = await health_line(session)
        return await send(session, chat, line)
    if low in ("reset", "forget", "new chat"):
        _history.pop(chat, None)
        return await send(session, chat, "Cleared. Starting fresh.")

    body = {"q": text, "history": [{"role": r, "content": c}
                                   for r, c in _history.get(chat, [])]}
    try:
        async with session.post(ASK_URL, json=body,
                                timeout=aiohttp.ClientTimeout(total=None,
                                                              sock_read=300)) as r:
            out = await r.json()
    except Exception as exc:
        return await send(session, chat,
                          f"I could not reach my own router ({type(exc).__name__}).")

    reply = (out.get("answer") or "").strip()
    if not reply:
        return await send(session, chat, "I have no answer for that.")
    remember(chat, "user", text)
    remember(chat, "assistant", reply)
    await send(session, chat, reply)


async def poll():
    """Long poll for updates. Outbound only; nothing listens here."""
    offset = None
    async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_read=90)) as session:
        asyncio.create_task(watch_health(session))
        while True:
            tok = token()
            if not tok:
                # No token yet is the normal state before enrolment, not an
                # error. Wait quietly rather than filling the log.
                await asyncio.sleep(30)
                continue
            try:
                params = {"timeout": 50}
                if offset is not None:
                    params["offset"] = offset
                async with session.get(
                        f"https://api.telegram.org/bot{tok}/getUpdates",
                        params=params) as r:
                    data = await r.json()
            except Exception:
                await asyncio.sleep(5)
                continue

            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                chat = str((msg.get("chat") or {}).get("id", ""))
                text = (msg.get("text") or "").strip()
                if not chat or not text:
                    continue
                if chat not in ALLOW:
                    # Their own ID is not a secret, and telling them is the
                    # only workable way to enrol a first user.
                    await send(session, chat,
                               "Not authorised. If you are meant to be, add "
                               f"chat id {chat} to NOVA_TG_ALLOW.")
                    continue
                if not rate_ok(chat):
                    await send(session, chat, "Too many messages. Give me a minute.")
                    continue
                asyncio.create_task(answer(session, chat, text))


if __name__ == "__main__":
    asyncio.run(poll())
