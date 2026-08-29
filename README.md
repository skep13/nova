# Nova

Voice chat UI for a local 3B model on a ThinkPad T470 (Proxmox, 8 GB RAM,
i5-6300U). Designed for a landscape, wrist-mounted iPhone reached over Tailscale.

## Deployed layout

    iPhone (Safari, on the tailnet)          Fedora laptop / iPad
      |  http (mic works; https not needed)     |
      v                                         v
    LXC 102 "tailscale"  192.168.1.235 / 100.108.27.102
      exit node + subnet router for 192.168.1.0/24
      |
      v
    LXC 101 "docker"     192.168.1.109   (5120 MB, 2 cores)
      web      nginx :8080 -> page, and one origin for everything below
      remote   agent router: local model or a free hosted one
      llama    Qwen2.5-3B-Instruct Q4_K_M
      embed    nomic-embed-text-v1.5, vault vectors
      piper    neural TTS
      whisper  whisper.cpp base.en, speech to text
      kiwix    offline Wikipedia + medical archives
      webdav   the vault, for Obsidian on any device

- **LAN URL: http://192.168.1.109:8080** — use this everywhere. The microphone
  works over plain http; https is not required and never was.
- HTTPS via `tailscale serve` exists as a fallback only.
- Stack lives in `/opt/orb` inside LXC 101.

Because LXC 102 is an approved subnet router, the LAN URL works off-site too,
without routing everything through the exit node.

Tailscale and Docker are in **separate** containers, so serve proxies across
the LAN rather than to localhost. Nothing is published to the internet;
`tailscale serve` is tailnet-only (that would be `funnel`, which must never be
enabled while the WebDAV endpoint is unauthenticated).

## Measured on this hardware

| | Cold (first request after start) | Warm |
|---|---|---|
| Prompt eval | ~5 tok/s | ~40 tok/s |
| Generation (3B) | ~6 tok/s | **~8.3 tok/s** |
| Speech to text (base.en) | | ~2.2 s |
| Research note, local model | | ~170 s |
| Research note, hosted agent | | ~5 s |

RAM went 4 GB -> 8 GB on 2026-08-17 and the model went 1.5B -> 3B with it. The
3B is exactly half the speed and was kept anyway: asked how much water to drink
hiking in heat, the 1.5B answered "1-2 litres per day", which is low enough to
be dangerous. The 3B answered 2.5-3. For a search-and-rescue device that is the
whole argument — the 1.5B is faster at being wrong.

**CPU is now the binding constraint, not RAM.** The i5-6300U is two physical
cores, so llama already saturates it at `-t 2`; more threads or more cores in
the LXC will not help.

## What runs

| Container | Job | RAM limit |
|---|---|---|
| `llama` | Qwen2.5-3B-Instruct Q4_K_M, OpenAI-compatible API, 8k context | 3500m |
| `remote` | agent router, vault search, `/research`, `/health`, geo | 256m |
| `kiwix` | full English Wikipedia (50 GB) + mdwiki-medicine (2.2 GB) | 1024m |
| `piper` | Piper neural TTS, `en_US-lessac-high` | 640m |
| `embed` | nomic-embed-text-v1.5, semantic vault search | 400m |
| `whisper` | whisper.cpp `base.en`, server-side speech to text | 500m |
| `webdav` | hacdias/webdav over the vault, for Obsidian | 96m |
| `web` | nginx: the page, and one origin for all of the above | 64m |

## Skills: answered exactly, not generated

Some things a small model does badly and a parser does perfectly. These are
handled in the browser before the model is invoked, so the answer is exact.

| Say | Get |
|---|---|
| `12 miles in km` | 12 miles is 19.312 km |
| `how many pounds in 70 kg` | 70 kg is 154.324 pounds |
| `convert 20 c to f` | 20 c is 68 f |
| `what is 17 * 43` | 731 |
| `(120 + 30) / 4` | 37.5 |
| `set a timer for 2 minutes` | Timer set |
| `remind me in 90 seconds to check the radio` | Labelled timer |
| `how long is left` | Remaining on each |
| `cancel all timers` | Cancelled |

Why this matters, from the actual transcript — the same expression asked twice:

    model:  (120 + 30) / 4  ->  27       wrong
    skill:  (120 + 30) / 4  ->  37.5     correct

Arithmetic is tokenised and parsed with a strict character whitelist — never
`eval`. Timers persist in `localStorage` with absolute end times, so they
survive iOS tearing the app down and fire correctly on relaunch.

## Preferences go in the system prompt

A stored preference used as a *description* in a mid-conversation block was
injected correctly and ignored anyway:

    fact in reference block  ->  "29,029 feet (8,848 meters)"
    same fact as a directive ->  "8,848 meters (29,029 feet)"

So any memory containing prefer/always/never/avoid is promoted into the main
system prompt as a standing instruction, and excluded from the reference block
to avoid duplication. Small models follow imperatives at the top far more
reliably than descriptions buried in context.

## Memory and your own notes

Everything lives as Markdown in `/opt/orb/mem/` inside LXC 101 — no database.
It is a real Obsidian vault: 343 notes, 28 maps of content, zero broken
wikilinks, synced to phone, iPad and laptop over WebDAV at `/dav/Orb/`.

nginx's own dav module serves the page's short facts, but it **cannot** serve
Obsidian — it does PUT and DELETE and returns 405 to PROPFIND, which is how a
client lists a directory. That is what the `webdav` container is for.

### Adding your own material

**Drop a `.md` file in `/opt/orb/mem/`.** That is the whole procedure — it is
picked up on the next page load. No import step, no restart.

```bash
pct exec 101 -- sh -c 'cat > /opt/orb/mem/my-project.md' <<'EOF'
---
title: Project name
---

Whatever you want it to know. Plain prose works best.
EOF
```

Optional frontmatter: `title:` (used for matching and shown in the trace line)
and `created:`. A leading `# Heading` is used as the title if no frontmatter.

### Facts vs notes — the important distinction

| | Length | Behaviour |
|---|---|---|
| **Fact** | ≤ 240 chars | Eligible for **every** prompt, up to 8 by relevance |
| **Note** | > 240 chars | **Retrieved** only when relevant, excerpted to ~900 chars |

This split exists because the context window is 8k. A 2000-word project brief
injected into every prompt would crowd out the conversation; retrieved on
demand it costs nothing until it is needed. A matching note also **outranks
Wikipedia** — it is your own material about your own work — and suppresses the
encyclopedia lookup for that turn so the model gets one source, not two that
may disagree.

Notes are excerpted *around the first matching term*, not from the top, so a
hit buried deep in a long note is still what gets injected.

### By voice or text

- `remember that I prefer metric units` — writes a new `.md`
- `forget marathon` — deletes every entry matching that text
- `forget everything` — clears the store
- `what do you remember` — lists facts and notes separately

Six high-precision patterns also capture facts automatically ("my name is …",
"I'm allergic to …", "I live in …"). Deliberately narrow: loose patterns fill
the store with junk, and junk enters every prompt.

As everywhere else here, **the model never decides what to remember** — capture
and retrieval are both deterministic, in the browser, before it is invoked.

## Research: the vault writes itself

Say **"research X"**, **"look up X"** or **"make a note on X"** and Nova searches
its own notes and the offline Wikipedia, writes the answer up, files it in the
vault, and streams it back. The note is cross-linked into everything already
there, so the graph grows with it.

Also `read up on X`, `study up on X`, `write a note about X`. It is deliberately
**only** these explicit verbs — every ordinary question would qualify as
something worth reading up on, and a vault that files a note on each of them
stops being a second brain within a week.

Same principle as everywhere else here: **the model never decides to search.**
It is not asked whether to look something up, what to look it up under, or
whether to save the result. The server queries the archive three ways (the raw
question, its key terms, and the title of the best matching note), ranks the
candidates by how much of the question their titles cover, and hands the model
only the text it found. The model's one job is to write prose from it, which is
the thing a 3B does well. There is no agent loop, so it cannot pick the wrong
tool — it never picks.

Two rules keep this from rotting the vault:

- **It cannot ground on its own output.** Ask the same question twice and the
  first note would otherwise be the best vault match for the second, so each
  pass would launder the last one's mistakes into a cited source. Generated
  notes are barred from being research sources — though they stay fully
  searchable in chat.
- **A generated note loses a close contest.** In retrieval its score is scaled
  by 0.7, so a hand-written field note wins where both match. Being written by
  a model is a reason to rank second, not a reason to be invisible.

Every research note says in its first line that a model wrote it, names the
sources in its frontmatter, and is tagged `research`. Provenance has to survive
being excerpted, because a 900-character window served back as an answer months
later carries no other context.

Expect **~170 s on the local model** for a 900-token note and a few seconds on a
hosted agent. It streams, so text appears as it arrives.

## Retrieval: lexical first, meaning second

Vault search is rarity-weighted whole-word matching with stemming and acronym
aliases, tuned over four rounds of real failures — substring matching had
"work" hitting net**work**; broad titles outranked specific ones until IDF was
added; "scheduler" missed "Scheduling" until stemming; "tls" missed Transport
Layer Security until acronym aliases.

Behind it sits a semantic fallback, and it is deliberately only a fallback.
Lexical hits are checked first and a confident one is never second-guessed —
measured on this vault, genuine questions score 11.9-20.8 and nonsense scores
5.7-8.1, so 8.0 is the line. Below it, the question is embedded and compared
against cached note vectors.

This exists for the query lexical retrieval structurally cannot answer: *"how
do i stop someone bleeding out"* shares no stemmable word with a note titled
**Bleeding**. On this device that is not an edge case.

Embeddings are cached against each note's mtime, so a restart re-embeds
nothing and an edited note re-embeds only itself. With the `embed` container
down, retrieval silently falls back to lexical alone.

## Health: knowing when something is broken

`GET /health` asks every subsystem a real question and reports what answered.

It exists because two failures were found by accident rather than by anything
noticing. The whisper container exited 127 on every start for days, because its
Dockerfile copied the binary without the shared libraries it linked against.
Groq retired a model mid-use and the agent 404'd. In both cases the page still
loaded and the orb still lit up.

So liveness means *answered a question*, not *the process exists* — `docker ps`
reported whisper "Up" the entire time it was crash-looping. llama is asked to
generate a token, not merely to list models, because it serves `/v1/models`
happily while weights are still loading.

The page polls it and shows a red chip **only when something is failing**. A
permanent green tick is noise you stop reading within a day, and then it is
worth nothing on the day it should have turned red.

`llama`, `kiwix` and the vault are critical; everything else degrades. Hosted
agents are reported but never counted — the device is supposed to work with
none of them.

## Backups

`nova-backup.sh` on the Proxmox host, nightly at 04:12, 30 days retained. It
tars `mem/`, `keys/`, `logs/` and the config out of the container — everything
the git repo deliberately excludes, which is exactly the set of files with no
second copy anywhere.

**This job silently did nothing for a week.** `pct` lives in `/usr/sbin`, and a
root *user* crontab runs with `PATH=/usr/bin:/bin` — it does not inherit the
PATH from `/etc/crontab`. The shell created the `.part` file by opening the
redirect, `pct` was not found, `set -e` aborted, and the crontab line ended in
`>/dev/null 2>&1` so nothing was ever reported. The last good backup predated
the entire vault.

Three things now prevent a repeat:

1. PATH is set inside the script and `pct` is called by absolute path.
2. The archive is verified to **contain notes**, not merely to be valid gzip —
   an empty tar is perfectly valid gzip, which is how you end up trusting a
   backup of nothing.
3. Success and failure are reported back into the container, `/health` reads
   the age, and the page shows a fault chip if it goes stale. A backup nobody
   checks is a backup that is not happening.

Backups live on the same physical disk as the thing they back up. Set
`NOVA_BACKUP_OFFBOX` to an scp target to get a copy off the box; an unreachable
target is logged, never fatal, because a sleeping laptop must not fail a backup.

Restore is `tar xzf` — verified end to end: 343 notes in, 343 notes out.

## Grounding: offline Wikipedia

A small model invents plausible-sounding facts. The single cheapest accuracy
win on this hardware is handing it a real article first.

**The model has no tools and makes no tool calls.** Verity measured
`qwen2.5:1.5b` at 2/5 on tool-use reliability, so leaving the decision to the
model would be the weakest link. Instead the page does it deterministically,
before the model is invoked:

1. Strip stopwords from the question (diacritics normalised, not deleted —
   a naive `[^a-z0-9]` replace turns "Kármán" into unusable fragments).
2. Skip entirely if the message is purely social ("hello", "thanks").
3. `GET /wiki/search?pattern=…` — ~113 ms.
4. Score the top 5 hits by **how much of the article title the question
   accounts for**. Require ≥ 0.6. Matching on a single shared word sent
   "hello there" to *Hello World (Belle Perez song)*.
5. Fetch the winner, take `<p>` text up to ~900 chars, prepend it as a system
   message marked as data-not-instructions.

Measured: injecting ~124 extra tokens cost **no additional time-to-first-token**
(3.76 s vs 3.89 s) — batch prompt processing absorbs it at this scale.

The article used is shown as a trace line in the transcript, so a wrong answer
is diagnosable instead of merely confident. The book button in the rail toggles
grounding off, and the choice is remembered.

Grounding improves accuracy; it does not make a 3B model reliable. It still
paraphrases loosely — expect the occasional detail to be off even with a
correct source in front of it.

**Bigger archives are nearly RAM-neutral** — kiwix mmaps the ZIM, so a larger
dump mostly costs disk. Swap the file in `zim/` and update the compose command.

## Voice (current)

**Primary: edge-tts** — Microsoft neural voices through Edge's read-aloud
endpoint. No API key, no account, free. Measured on this box:

| | Piper high (was) | edge-tts (now) |
|---|---|---|
| Latency | 2.5 s | **0.36–1.58 s** |
| Local CPU | both cores | **none** |
| Container RAM | 280 MB | **34 MB** |

Offloading synthesis also gives llama back the two cores it was sharing.

Voices (all female): `ava` (default), `emma`, `aria`, `michelle`, `jenny`,
`sonia`, `libby`, `maisie`. Say `voice sonia` and it speaks a sample.

**Fallback: Piper**, still deployed and served at `/tts-local`. The client
switches to it automatically if edge is unreachable, so the box keeps talking
with no internet. That is the entire reason it is still there.

Caveats: the endpoint is undocumented and could change, and text leaves the
network. Neither applies to the Piper path.

### Audio processing — all off by default

Three attempts at a filter chain (synthetic sheen, a GLaDOS-style ring
modulator, then broadcast polish) each made the voice worse: thin and phasey,
then crackly from summing paths without headroom, then crackly again from
makeup gain above unity. Everything now defaults to off and you hear raw
synthesis. `voice robot <n>` and `voice polish <n>` remain, clipping fixed,
if ever wanted.

## Voice (Piper, fallback path)

**Out** — Piper, hosted in Docker, so the voice is the same female voice on any
device instead of whatever the phone provides. Measured on this CPU: **RTF
0.13** (0.65 s of compute for 5.15 s of audio), so synthesis stays comfortably
ahead of 13 tok/s generation and audio starts in well under a second.

The page probes `/tts` once at startup. If Piper is unreachable it silently
falls back to the phone's own voice, preferring a female one (Samantha on iOS,
Zira on Windows). Stopping the `piper` container is therefore safe — you just
lose voice consistency, not audio.

Server audio plays through the Web Audio graph rather than an `<audio>` tag,
which means the orb pulses to the **actual waveform** while it speaks. The
device path can't do that.

### Voice bank

Four female English voices ship in the image and are selected per request via
Piper's `voice` field — no rebuild needed to try another:

| Say | Voice |
|---|---|
| `voice list` | Show all, current voice, effect state |
| `voice kristin` | US, bright (default) |
| `voice amy` | US, warmer |
| `voice clear` | US, neutral |
| `voice jenny` | British, young |
| `voice off` / `voice on` | Synthetic effect off/on |

Each switch speaks a sample line so it can be judged by ear. The choice is
remembered.

### Synthetic colouring

Server audio already plays through the Web Audio graph, so a filter chain gives
the assistant-AI character without touching the model: a 135 Hz high-pass to
thin the chest tone, +3.5 dB presence at 2.1 kHz, a +4.5 dB air shelf, and a
short LFO-modulated delay (~13 ms, 30 % wet) for a digital shimmer, into gentle
compression.

This is **colouring, not impersonation** — no model here reproduces any
particular performer, and training a voice model is far outside what two cores
can do.

**Memory note:** every voice auditioned stays resident (~60 MB each); the
server caches loaded voices rather than swapping them, which is why the cap is
560 MB. Once settled on one, set it as `VOICE_MODEL` in `Dockerfile.piper` and
restart to drop back to ~230 MB.

**In** — Safari's Web Speech API, on the phone. See below.

Speech-to-text runs **on the iPhone**, not the server. Safari's Web Speech API
handles dictation, `speechSynthesis` handles spoken replies, and the T470 only
ever does token generation.

## Deploy

Copy the whole directory to the Docker host, then:

```bash
docker compose up -d
```

First run pulls the ~1.1 GB GGUF. Nothing is compiled.

## HTTPS (done, kept for reference)

**Correction (2026-08-18): https is NOT required for speech input.** The
original claim here was that iOS exposes the mic only in a secure context. That
is true of `getUserMedia`, which the record-and-transcribe fallback uses — it is
not true of `webkitSpeechRecognition`, which goes through the system speech
service and works over plain http on the LAN. Tested on the device: dictation
works fine at http://192.168.1.109:8080.

So the page now warns about a missing secure context only when it is actually
on the record path. It previously showed "needs https — mic blocked on http" on
every plain-http load, which was wrong and contradicted by the hardware.

https is still worth having for a different reason: Tailscale Serve is what
makes the orb reachable away from the LAN at all.

Serve had to be enabled once for the tailnet via the admin console; there is no
CLI path for it, which is why `tailscale serve` prints a link and blocks. It is
enabled now. The command that configured it, run inside LXC 102:

```bash
tailscale serve --bg http://192.168.1.109:8080
```

To undo:

```bash
tailscale serve --https=443 off
```

Certificates live in `/var/lib/tailscale/certs/` and renew automatically.

## The phone must be on the tailnet

All the iPhones in this tailnet currently show as offline. Open the Tailscale
app on the phone and connect before the URL will resolve.

## Add to Home Screen (do this — it is not optional for wrist use)

In Safari: Share -> Add to Home Screen, then launch from the icon.

Landscape gives you ~393 px of height. Safari's chrome eats roughly 100 px of
that — about a quarter of the screen, on the axis you have least of. Launched
from the home screen the page runs standalone and gets all of it. The manifest
and `apple-mobile-web-app-capable` tag are already set up for this.

The icon is the orb itself, generated by `make_icon.py` from the same gradient
stops the page uses.

## Using it

Landscape is the layout, not a variant — the phone is wrist mounted and never
turns. The shell is `orb | transcript | rail`, so the transcript gets the full
393 px of height instead of losing ~57 px to a bottom bar. Portrait exists only
so the page is not broken if the orientation sensor disagrees for a moment.

- Tap the orb — the entire left pane (~324 px wide, full height) is the target.
- **Long-press the orb (0.65 s) clears the conversation.** There is no room for
  a delete button, and without this the only way to start over is a reload.
- **Speaker button** (rail) toggles spoken replies. Muted, it shows a slash and
  the status reads "text only": you still speak to it, replies arrive as text
  in the transcript and nothing is synthesized. **The choice is remembered
  across launches.**
- **Keyboard button** (rail) reveals the text input, hidden by default — a
  keyboard covers most of a landscape phone, so it does not earn permanent
  space on a device driven by voice.
- Tapping while it is talking cuts it off and starts listening (barge-in).
- Short tones confirm the mic opening and closing, so you can use it without
  looking at the screen.

There is no hands-free mode. iOS requires a user gesture to start speech
recognition, so an auto re-arm after each reply cannot work — a button that
does nothing is worse than no button on a wrist.

The conversation is saved to `localStorage` and restored on launch — iOS tears
down home-screen web apps aggressively, and without this every glance at your
wrist would start from an empty screen.

Wake Lock keeps the screen awake after your first tap. Because that would
otherwise burn battery all day, the screen fades to black after 45 s idle and
any tap wakes it — that first tap only wakes, it does not open the mic. The
panel is OLED, so this is a real power saving rather than a cosmetic one.

The dot beside the speaker button turns red if the model becomes unreachable.

## If you ever want local-only speech

Safari sends dictation audio to Apple. To keep audio on the T470 instead, a
whisper.cpp service is defined behind a compose profile:

```bash
docker compose --profile stt up -d --build
```

That builds whisper.cpp from source (~5 min on this CPU) and costs ~320 MB.
nginx resolves the whisper host at request time, so `/stt` simply returns 502
while the profile is off and everything else keeps working. Note the page only
uses this path on browsers without the Web Speech API — on Safari you would
also need to force it.

## Tuning

- `-t 4` vs `-t 2`: the i5-6300U is 2 cores / 4 threads and this workload is
  memory-bandwidth-bound, so hyperthreading may buy nothing. Measure both.
- Expect **~8-11 tok/s** at 4 GB single-channel. Filling the free SO-DIMM slot
  gets you dual-channel and roughly doubles it.
- Replies are capped at 300 tokens and the system prompt asks for one or two
  sentences — at this speed long answers are unusable on a wrist.
- History is trimmed to the last 12 turns to stay inside the 4k context.
