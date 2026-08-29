"""Write Nova's notes about Nova, into Nova's own vault.

Self-diagnosis is a retrieval problem before it is anything else. Asked "why did
my backup fail", a model with no notes about this system can only produce
plausible-sounding generic advice — and generic advice about a bug caused by a
root user crontab's PATH is worse than silence, because it sounds right.

So these are written by hand and deliberately specific: real paths, real
container names, real symptoms, and the recovery procedure that actually works
on this box. Where something has failed before, the note says so and says how it
was found, because the second occurrence is always easier to spot than the first.

Hand-written rather than fetched: Wikipedia does not know what /dav/Orb is.

Runs inside LXC 101. Re-runnable; it overwrites its own notes and nothing else.
"""
import datetime
import pathlib
import re

MEM = pathlib.Path("/opt/orb/mem")
NOW = datetime.datetime.now().isoformat(timespec="seconds")

NOTES = {
"nova-architecture": ("Nova architecture", """
Nova runs as eight containers inside LXC 101 (192.168.1.109) on a ThinkPad T470
under Proxmox. Everything lives in /opt/orb. One nginx serves the page and
proxies every other service, so the browser only ever talks to one origin.

web serves the page and proxies everything. remote is the agent router and owns
vault search, research, health and position; it listens on port 5003 and is the
only service with application logic in it. llama runs the local model. embed
runs the embedding model for semantic search. piper synthesises speech. whisper
transcribes it. kiwix serves the offline Wikipedia. webdav exposes the vault to
Obsidian.

Only web publishes a port. Everything else is reachable only on the internal
docker network by service name, which is why the router addresses them as
http://llama:8080 and http://piper:5000 rather than by address.

The stack is deliberately one machine. Splitting the model across nodes was
considered and rejected: the model already fits in RAM, and llama.cpp's RPC
backend exists to run models that do not fit, so adding workers would only add
network overhead.

Related: [[nova-endpoints|Nova endpoints]], [[nova-recovery|Nova recovery procedures]]
"""),

"nova-endpoints": ("Nova endpoints", """
Every route is served through nginx on port 8080 and proxied to the container
that owns it.

The page itself is at /. Chat goes to /v1/chat/completions, which the router
intercepts to choose a backend. /agents lists the available backends and why any
are unavailable. /recall searches the vault and returns one excerpt. /research
searches vault and archive, writes the answer up and files it as a note.
/ingest accepts a document upload and turns it into a note. /health probes every
subsystem. /place turns coordinates into a place name. /diag accepts a beacon
from the page recording which speech mode it is using. /tts synthesises speech,
/stt transcribes it. /wiki/ is the offline Wikipedia. /mem/ is the short-facts
store the page reads directly. /dav is the vault over WebDAV.

Two of these have caught people out. /recall is a GET with a q parameter, not a
POST — posting to it returns 405. And /research streams, so it returns an SSE
stream rather than JSON, with a trailing event naming the note it filed.

A route that exists in the router but not in nginx returns 405 rather than 404,
because the request falls through to the static file handler. That is what
happens when a new endpoint is added to remote_proxy.py and nginx.conf is
forgotten.

Related: [[nova-architecture|Nova architecture]], [[nova-agents|Nova agents]]
"""),

"nova-agents": ("Nova agents", """
The router offers several backends and guarantees an answer from any of them.

local is llama.cpp in the next container, running Qwen2.5-3B-Instruct Q4_K_M
with an 8k context and two threads. It is always available and is the default.
fast is Groq. deep is OpenRouter. wide is NVIDIA. long is Google AI Studio,
which gets its own larger token budget because its models reason before
answering and that thinking is billed against max_tokens while never being
shown.

Every hosted backend is free and none of them bills. Keys live one per file in
/opt/orb/keys/<agent>.key, mounted read-only into the container at /run/keys. An
agent with no key file is never offered — there is no half-configured state.

Any remote failure falls back to local silently. The response is only prepared
after the upstream has answered 200, which is what makes the fallback invisible
rather than leaving half a reply on screen.

Configuration failures are treated differently from transient ones. A 401, 402,
403 or 404 means the account or the model ID is wrong and will fail identically
every time, so that agent is withdrawn for ten minutes. A 429 is a rate limit
and is not withdrawn, because falling back for one request is the right
response. Hosted model IDs are environment variables rather than code, because
providers retire models without warning — which Groq did mid-use.

Related: [[nova-endpoints|Nova endpoints]], [[nova-recovery|Nova recovery procedures]]
"""),

"nova-vault": ("Nova vault", """
The vault is /opt/orb/mem — plain Markdown, no database. It is simultaneously
the assistant's knowledge and a real Obsidian vault synced to phone, iPad and
laptop.

Notes are separated by length. Anything at or under 240 characters is a fact
about the user and is injected into every prompt; anything longer is a document
and is retrieved only when relevant, excerpted to about 900 characters around
the first matching term. This split exists because the context window is 8k: a
long note injected every turn would crowd out the conversation.

On top sits a hub layer of maps of content, tagged moc, giving index then
domain then topic then note. Hubs exist for Obsidian's graph view, which is a
force simulation with no manual layout, so link topology is the only thing that
organises it. Hubs are excluded from retrieval: a hub is a list of links
carrying every term in its topic, so it would outrank the note that answers and
then reply with an index.

Wikilinks must be written as slug-then-pipe-then-display-text inside double square brackets. Obsidian resolves a link
against the file name, and these files are slugs while the prose is not.
Writing a link whose target is the prose name, against a file saved as operating-system.md, is what once left 1308
of 2073 links pointing at nothing.

Related: [[nova-retrieval|Nova retrieval]], [[nova-recovery|Nova recovery procedures]]
"""),

"nova-retrieval": ("Nova retrieval", """
Finding the right note happens in two stages, and the first one is the one that
usually works.

Lexical search scores notes by rarity-weighted whole-word matching, with suffix
stemming so scheduler reaches Scheduling, and acronym aliases so tls reaches
Transport Layer Security. An acronym outranks a title word deliberately: DNS is
a literal title word of DNS spoofing but only an alias of Domain Name System,
and someone asking what DNS is wants the latter.

Semantic search runs only when lexical is not confident. Measured on this vault,
genuine questions score 11.9 to 20.8 lexically and nonsense scores 5.7 to 8.1,
so 12 is the line above which the lexical answer is taken unexamined. Below it
the question is embedded and compared against cached note vectors, and the
vector only wins if it clears 0.70.

The honest measurement: across a broad set the two are a wash, 7 of 12 either
way. Semantic earns its place on field questions, where lexical answered "what
happens to your body at very high places" with Drowning and "when your body
loses too much water" with Survival skills.

Notes the assistant wrote itself are scored at 0.7 and are barred entirely from
being research sources, so it cannot cite its own previous output as
corroboration.

Related: [[nova-vault|Nova vault]], [[nova-research|Nova research]]
"""),

"nova-research": ("Nova research", """
Saying research, look up, read up on, or make a note on followed by a topic
makes Nova search its own notes and the offline Wikipedia, write the answer up,
file it as a note, and stream it back.

The model never decides to search. It is not asked whether to look something up,
what to look it up under, or whether to save the result. The server queries the
archive three ways — the raw question, its key terms, and the title of the best
matching vault note — ranks candidates by how much of the question their titles
cover, and hands the model only the text it found. There is no agent loop, so it
cannot pick the wrong tool: it never picks.

A relevance floor stops it writing notes about nothing. kiwix does full-text
search and returns something for any string, so a source must share a word with
the question's title, and how much overlap is required scales with how much was
asked — one shared word out of two is a match, one out of five is a coincidence.

Every research note says in its first line that a model wrote it and names its
sources in frontmatter. Provenance has to survive being excerpted, because a
900-character window served back as an answer months later carries no other
context.

Expect about 170 seconds on the local model and a few seconds on a hosted one.

Related: [[nova-retrieval|Nova retrieval]], [[nova-vault|Nova vault]]
"""),

"nova-backups": ("Nova backups", """
nova-backup.sh runs on the Proxmox host at 04:12 nightly, keeping 30 days in
/var/backups/nova. It archives mem, keys, logs and the config out of the
container — everything the git repo deliberately excludes, which is exactly the
set of files with no second copy anywhere.

This job silently did nothing for a week, and the way it failed is worth
remembering. pct lives in /usr/sbin, and a root user crontab runs with
PATH=/usr/bin:/bin — it does not inherit the PATH set in /etc/crontab. The shell
created the .part file by opening the redirect, pct was then not found, set -e
aborted, and the crontab line ended in redirect-to-null so nothing was reported
anywhere. The tell was in the timestamps: the two successful archives were
stamped 23:37 and 00:25, not 04:12, so they were manual runs. Cron had never
worked.

Three things now prevent a repeat. PATH is set inside the script and pct is
called by absolute path. The archive is verified to contain at least fifty notes
rather than merely to be valid gzip, because an empty tar is perfectly valid
gzip. And the result is written back into the container, where /health reads its
age and the page shows a fault chip if it goes stale.

Restore is tar xzf into a scratch directory, then compare the note count with
the live vault before trusting it.

Related: [[nova-health|Nova health]], [[nova-recovery|Nova recovery procedures]]
"""),

"nova-health": ("Nova health", """
/health asks every subsystem a real question and reports what answered.

It exists because two failures were found by accident rather than by anything
noticing. The whisper container exited 127 on every start for days, because its
Dockerfile copied the binary without the shared libraries it linked against.
Groq retired a model mid-use and that agent started returning 404. In both cases
the page still loaded and the orb still lit up.

So liveness means answered a question, not the process exists — docker ps
reported whisper Up for the entire time it was crash-looping. llama is asked to
generate a token rather than to list models, because it serves /v1/models
happily while the weights are still loading.

llama, kiwix and the vault are critical and return 503 if they fail. Everything
else degrades: piper, whisper, webdav, embeddings and backup age are reported
but do not make the device unusable. Hosted agents are reported and never
counted, because the device is supposed to work with none of them.

The page polls it every five minutes while visible and shows a red chip only
when something is failing. A permanent green tick is noise you stop reading
within a day, and then it is worth nothing on the day it should have turned red.

Related: [[nova-recovery|Nova recovery procedures]], [[nova-backups|Nova backups]]
"""),

"nova-voice": ("Nova voice", """
Speech in has two paths and the page picks between them at load.

In Safari it uses the browser's own recognition. Launched from the iOS home
screen it cannot: webkitSpeechRecognition constructs, starts, and ends within a
few hundred milliseconds with no result and no error, which is
indistinguishable from saying nothing unless the timing is measured. In that
case the page records audio and sends it to whisper instead.

Ending the turn is decided by Nova, not by the browser. Safari is supposed to
stop recognition when you stop talking and frequently does not, leaving the
session open until something else happens to the page — which is why it used to
need a screen tap to notice you had finished. The gap between interim results
is timed instead: 1.5 seconds of quiet ends the turn, with 8 seconds allowed
before the first word because pausing to think is normal. The recording path
does the same thing on the audio thread rather than in an animation frame,
because animation frames stop when the display dims.

Speech out is Piper with en_US-lessac-high and all post-processing off. Four
attempts at colouring it made it worse each time.

Transcription is whisper.cpp base.en, not tiny.en. tiny heard "grid reference"
as "great reference", and that is a regex-matched command, so a mis-hearing does
not degrade an answer — it silently removes a feature.

Related: [[nova-architecture|Nova architecture]], [[nova-recovery|Nova recovery procedures]]
"""),

"nova-deploying": ("Nova deploying a change", """
Files live in /opt/orb inside LXC 101. What you do after editing one depends on
how that file reaches its container.

index.html, nginx.conf and manifest.json are bind-mounted read-only into the web
container. A page change needs no restart at all — reload the browser, hard, as
iOS holds the home-screen copy across launches. An nginx.conf change needs
nginx -t then nginx -s reload inside the web container.

remote_proxy.py is COPIED into the remote image at build time, not mounted. It
must be rebuilt: docker compose up -d --build remote. Using --force-recreate
alone restarts the container with the old code still inside it, which looks
exactly like the change having no effect.

docker-compose.yml changes need docker compose up -d for the affected service.
Anything touching the whisper or piper Dockerfiles needs --build.

The vault needs no deployment step: notes are read from disk on every query, and
the loader checks the directory's modification time rather than the contents, so
it is cheap enough to check every time.

Related: [[nova-architecture|Nova architecture]], [[nova-recovery|Nova recovery procedures]]
"""),

"nova-recovery": ("Nova recovery procedures", """
Symptoms, causes and what to do, for the failures this system has actually had.

Model unreachable, or the page says so: llama is down or still loading weights.
Check /health first — it asks llama to generate a token, which is a stronger
test than the page's own ping. Restart with docker compose up -d llama and give
it a minute.

An agent stops working and /agents shows a 404: the provider retired that model.
The router withdraws the agent automatically for ten minutes and names the cause
in last_error. Pick a replacement model ID and set it in docker-compose.yml —
these are environment variables precisely so this is a restart, not a rebuild.

Backup shows stale in /health: check the cron log at /var/backups/nova/cron.log.
The historical cause was PATH in a root user crontab. Run the script by hand to
see the real error; it now reports failures rather than swallowing them.

Obsidian shows no notes: Remotely Save uses the vault name as its remote folder
when the box is left empty, so it looks in /dav/Orb rather than /dav. The server
mounts the vault at /data/Orb specifically to match that.

A bulk vault change trips Obsidian's changed-files guard: this is correct
behaviour, not a fault. Raise the ratio to 1, sync, and set it back to 0.5.

Semantic search returns nothing: the embed container is down. Retrieval falls
back to lexical automatically, so this degrades quality rather than breaking
anything. Restart embed, then restart remote to rebuild the vectors.

A code change appears to do nothing: remote_proxy.py is copied into the image at
build time. Rebuild it.

Related: [[nova-health|Nova health]], [[nova-deploying|Nova deploying a change]], [[nova-backups|Nova backups]]
"""),

"nova-design-rules": ("Nova design rules", """
The rules this system is built on, and why each one exists. These are not
preferences; each was learned from something that went wrong.

The model never decides anything it is unreliable at. Retrieval, memory capture,
arithmetic, unit conversion, timers, position and greetings are all decided
deterministically before the model is invoked. A small model asked to choose a
tool chooses badly, and a wrong choice is invisible until it matters.

Offline is the default, not the fallback. Local answers everything unless a
hosted backend is deliberately selected, and any remote failure lands back on
local rather than surfacing an error.

Exactness beats generation. Asked to evaluate (120 + 30) / 4 the model answered
27; the parser answered 37.5. Anything a parser can do perfectly is not asked of
the model.

Never animate a property the compositor cannot handle. Animating filter blur
re-rasterises the layer every frame, which on two cores is visible stutter.
Cross-fade two pre-blurred layers instead.

One transform per element. Two animations writing transform on the same element
means one silently wins, which is what once stopped the orb reacting to the
microphone.

A failure that reports nothing will not be noticed. Both the whisper crash-loop
and the dead backup ran for days because their failure path was silent.

Related: [[nova-architecture|Nova architecture]], [[nova-retrieval|Nova retrieval]]
"""),
}


def main():
    MEM.mkdir(parents=True, exist_ok=True)
    written = 0
    for stem, (title, body) in NOTES.items():
        doc = ("---\n"
               f"created: {NOW}\n"
               f"title: {title}\n"
               "tags: [nova, reference]\n"
               "source: hand-written\n"
               "---\n\n"
               f"# {title}\n\n{body.strip()}\n")
        (MEM / f"{stem}.md").write_text(doc, encoding="utf-8")
        written += 1

    # The six original notes are tagged orb; the system is called Nova now and
    # one self-domain is better than two.
    retagged = 0
    for p in MEM.glob("orb-*.md"):
        raw = p.read_text(encoding="utf-8", errors="replace")
        new = re.sub(r"^(tags:\s*\[)orb\b", r"\1nova", raw, count=1, flags=re.M)
        if new != raw:
            p.write_text(new, encoding="utf-8")
            retagged += 1

    print(f"  self-knowledge notes written: {written}")
    print(f"  legacy orb notes retagged   : {retagged}")


main()
