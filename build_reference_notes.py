"""Dense reference notes, written rather than fetched.

The vault is mostly Wikipedia, which is a problem hiding in plain sight: the
model was trained on Wikipedia. Those notes buy grounding, citation and offline
availability, but almost no new information — the model already knew most of it.

What it does NOT already have to hand, and what an encyclopedia is genuinely bad
at, is dense operational reference. Wikipedia's article on HTTP explains what a
status code IS; it will not tell you what 422 means at three in the morning.
Cheatsheets are a different shape of knowledge: lookup tables, not prose.

Written directly rather than researched, for two reasons. Accuracy — these are
stable facts I can state without a source round-trip, and a scraped cheatsheet
is a worse cheatsheet. And format — retrieval returns a 900-character window, so
a note built as a compact table survives excerpting in a way an article does
not.

Nothing here is invented. Where a value is version-dependent or I am not certain
of it, it is left out rather than guessed, because a reference note that is
wrong is worse than one that is missing.
"""
import datetime
import pathlib
import re

MEM = pathlib.Path("/opt/orb/mem")
NOW = datetime.datetime.now().isoformat(timespec="seconds")

NOTES = {
# ---------------------------------------------------------------- networking
"ref-http-status-codes": ("HTTP status codes", "ref, cs", """
The ones that come up, and what they actually mean as opposed to how they are
usually misused.

200 OK. 201 Created, and the response should carry a Location header. 204 No
Content, used for a successful DELETE or a PUT that returns nothing. 206 Partial
Content, for range requests.

301 Moved Permanently, cached hard by browsers and very difficult to undo. 302
Found, a temporary redirect that changes the method to GET. 307 and 308 are the
same as 302 and 301 but preserve the method, which is what you want for POST.
304 Not Modified, the answer to a conditional request.

400 Bad Request, malformed. 401 Unauthorized actually means unauthenticated —
you have not proved who you are. 403 Forbidden means authenticated and still not
allowed. 404 Not Found. 405 Method Not Allowed, which is what a route reachable
by GET returns to a POST — nginx returns it when a path falls through to a
static handler. 409 Conflict. 413 Payload Too Large. 415 Unsupported Media Type.
422 Unprocessable Content, syntactically valid but semantically wrong. 429 Too
Many Requests, and the Retry-After header is the useful part.

500 Internal Server Error, the catch-all. 502 Bad Gateway, an upstream returned
something invalid. 503 Service Unavailable, usually overloaded or starting up.
504 Gateway Timeout, an upstream did not answer in time.

The pair worth remembering: 401 is who are you, 403 is I know who you are and
the answer is still no.
"""),

"ref-common-ports": ("Common network ports (postgres, mysql, redis, ssh)", "ref, cs", """
20 and 21 FTP, 22 SSH, 23 telnet, 25 SMTP, 53 DNS, 67 and 68 DHCP, 80 HTTP,
110 POP3, 123 NTP, 143 IMAP, 161 SNMP, 389 LDAP, 443 HTTPS, 445 SMB,
465 SMTPS, 514 syslog, 587 SMTP submission, 636 LDAPS, 993 IMAPS, 995 POP3S.

Databases: 1433 SQL Server, 1521 Oracle, 3306 MySQL and MariaDB, 5432
PostgreSQL, 6379 Redis, 27017 MongoDB, 9200 Elasticsearch.

Infrastructure: 2049 NFS, 3000 common dev servers and Grafana, 3389 RDP,
5000 and 5001 various, 5900 VNC, 8000 and 8080 alternate HTTP, 8443 alternate
HTTPS, 9090 Prometheus, 11211 memcached.

Ports below 1024 are privileged on Unix: binding one requires root or the
CAP_NET_BIND_SERVICE capability, which is why containers so often serve on 8080
and are published on 80.
"""),

"ref-file-permissions": ("chmod and Unix file permissions", "ref, cs", """
Three triads: owner, group, other. Each is read 4, write 2, execute 1, summed.

644 is rw-r--r--, the default for a file. 755 is rwxr-xr-x, the default for a
directory or a script. 600 is rw-------, for anything secret — a private key or
an API key. 700 for a directory only you should enter. 777 is almost always
wrong and usually means the actual problem was ownership.

On a DIRECTORY the bits mean something different from a file. Read lists the
names inside it. Write creates and deletes entries, which is why you can delete
a file you cannot write to. Execute permits traversing into it, so a directory
with r but no x lets you see names and reach nothing.

Special bits, prepended: 4000 setuid, run as the file's owner. 2000 setgid, and
on a directory it makes new files inherit the group. 1000 the sticky bit, which
on a world-writable directory such as /tmp means only the owner of a file may
delete it.

umask subtracts. A umask of 022 gives 644 for files and 755 for directories; 077
gives 600 and 700, which is what a script handling secrets should set.
"""),

# ------------------------------------------------------------------- shell
"ref-shell-exit-codes": ("Shell exit codes, set -e and errors", "ref, code", """
0 is success and everything else is failure. That inversion is the source of
most shell bugs.

1 general error. 2 misuse of a builtin, often a syntax problem. 126 the command
was found but is not executable. 127 command not found — which is what a missing
shared library looks like too, because the loader fails before main runs. 128+n
means killed by signal n, so 130 is SIGINT (Ctrl-C), 137 is SIGKILL, and 143 is
SIGTERM. 137 in a container almost always means the memory limit was hit.

set -e exits on the first failure, and its exceptions matter: it does not fire
inside a condition, inside && or || except at the end, or on a failure in a
pipeline that is not the last command. set -o pipefail fixes the last of those.
set -u errors on an unset variable. set -x traces.

A redirect is opened BEFORE the command runs, so `cmd > out` creates out even if
cmd does not exist. That is how a failed backup leaves a zero-byte file behind.

$? is the last exit code and is overwritten by the next command, including the
one in your if. Capture it immediately or not at all.
"""),

"ref-regex": ("Regular expression syntax", "ref, code", """
. any character except newline. ^ start, $ end — of the string, or of a line
with the multiline flag. \\b word boundary.

Classes: \\d digit, \\w word character (letter, digit, underscore), \\s
whitespace; the capitals \\D \\W \\S are their negations. [abc] any of, [^abc]
none of, [a-z] a range.

Quantifiers: * zero or more, + one or more, ? zero or one, {n} exactly, {n,}
at least, {n,m} between. All are greedy; a trailing ? makes them lazy, so .*?
stops at the first match rather than the last.

Groups: (...) captures, (?:...) groups without capturing, (?P<name>...) names
it in Python. Alternation | has the lowest precedence, so ^a|b means "starts
with a, or contains b" — not what most people intend.

Lookaround matches without consuming: (?=...) followed by, (?!...) not followed
by, (?<=...) preceded by, (?<!...) not preceded by. Lookbehind must be
fixed-width in most engines.

The classic mistake is that lookaround does not protect against a match INSIDE
something already rewritten: replacing in a loop can find a target inside a
replacement it made a moment earlier.
"""),

"ref-git": ("Git commands worth knowing", "ref, code", """
Undoing, which is what people actually need.

git restore <file> discards uncommitted changes to it. git restore --staged
<file> unstages without discarding. git reset --soft HEAD~1 undoes the last
commit and keeps everything staged; --mixed keeps the changes unstaged; --hard
throws them away and is the only one that loses work.

git revert <commit> makes a NEW commit undoing an old one, which is the correct
way to undo something already pushed. Rewriting published history is what
--force-with-lease is for, and it is safer than --force because it refuses if
someone else has pushed since you fetched.

git reflog is the safety net: it records where HEAD has been, including commits
no branch points at any more, so an accidental reset --hard is usually
recoverable for ninety days.

Inspecting: git log --oneline --graph --all. git log -S"text" finds commits that
added or removed a string. git blame -L 10,20 <file>. git diff --staged shows
what a commit would contain.

git stash saves dirty state; git stash pop restores it. Untracked files need
git stash -u or they are left behind.
"""),

# ----------------------------------------------------------------- containers
"ref-docker": ("Docker and Compose in practice", "ref, ops", """
docker compose up -d starts in the background. --build rebuilds images first,
and this is the one people miss: if a Dockerfile COPIES source in, a plain
restart runs the OLD code and looks exactly like the change having no effect.
--force-recreate recreates containers without rebuilding images, which is a
different thing entirely.

docker compose logs -f <service> follows. docker compose ps shows status.
docker stats --no-stream is a snapshot of memory and CPU per container.

Exit 137 is the memory limit. Exit 127 is command not found, which for a
compiled binary usually means a missing shared library rather than a missing
file. A container that restarts endlessly with no logs is often failing before
its entrypoint.

Volumes: a named volume persists and is managed by Docker; a bind mount maps a
host path. Mounting at the wrong path is silent — the container writes to its
own layer, everything works, and the data vanishes when the container is
recreated.

docker system df shows what is using disk. docker image prune -f removes
dangling images; builder prune removes the build cache, which is usually the
largest single item and the least missed.

An internal: true network has no gateway attached, so containers on it alone
cannot reach anything outside the host. That is the primitive behind a sandbox.
"""),

"ref-systemd": ("systemd units and journalctl", "ref, ops", """
systemctl start, stop, restart, reload. enable makes it start at boot; disable
does not stop it now. enable --now does both. status shows recent logs with it.
daemon-reload is required after editing a unit file and is the step people
forget — systemd carries on running the old definition without complaint.

Unit files live in /etc/systemd/system for local ones. A minimal service needs
[Unit] Description, [Service] ExecStart, and [Install] WantedBy=multi-user.target.
Restart=always with RestartSec=5 handles a crashing process. Type=simple means
the ExecStart process IS the service; Type=forking is for daemons that background
themselves and gets misused constantly.

Hardening worth applying by default: NoNewPrivileges=yes, ProtectHome=yes,
ReadWritePaths= to list the only paths it may write.

journalctl -u <unit> for one unit, -f to follow, -n 50 for the last fifty,
--since "10 min ago", -p err for errors only. journalctl --disk-usage and
--vacuum-time=7d to reclaim space.

A timer is a separate unit with the same name and a .timer suffix, and it is the
modern replacement for cron. It logs where cron silently does not.
"""),

"ref-cron": ("cron and crontab: syntax, and why a job silently fails", "ref, ops", """
Five fields: minute, hour, day of month, month, day of week. 0 4 * * * is 04:00
daily. */15 * * * * is every fifteen minutes. 0 4 * * 1 is 04:00 on Mondays.
Day-of-week 0 and 7 are both Sunday.

Day-of-month and day-of-week are OR, not AND, when both are set. 0 0 13 * 5 runs
on the 13th AND on every Friday, not only on Friday the 13th.

The trap that costs the most: a user crontab runs with a minimal PATH, typically
/usr/bin:/bin, and does NOT inherit the PATH in /etc/crontab. A command in
/usr/sbin or /usr/local/bin will not be found. Set PATH explicitly at the top of
the crontab, or call binaries by absolute path.

The second trap: > /dev/null 2>&1 on the crontab line discards the error that
would have told you. Redirect to a log file instead. A job that fails silently
every night for a week is the normal outcome of these two together.

% in a crontab is a newline unless escaped as \\%, which breaks any date format
string. Cron does not run jobs missed while the machine was off; anacron or a
systemd timer with Persistent=true does.
"""),

# ------------------------------------------------------------------- python
"ref-python-stdlib": ("Python standard library, the useful corners", "ref, code", """
pathlib over os.path: Path("a") / "b", .read_text(), .write_text(), .exists(),
.glob("*.md"), .rglob for recursive, .stem, .suffix, .parent. .unlink(missing_ok=True)
deletes without raising if absent.

collections: Counter for frequencies with .most_common(n), defaultdict to avoid
key checks, deque for a fast queue with maxlen for a rolling window.

itertools: chain, groupby (which requires sorted input and surprises everyone),
islice, product, combinations.

functools: lru_cache and cache as decorators, partial, reduce.

dataclasses for structured records without boilerplate; field(default_factory=list)
because a mutable default is shared between instances.

contextlib: contextmanager to write one with a yield, suppress(Exception) instead
of a bare try/pass.

subprocess.run(list_of_args, capture_output=True, text=True) — pass a list, not a
string, and never shell=True with anything a user supplied.

json.dumps(obj, indent=2), and json.loads is strict about trailing commas.

Timing: time.monotonic() for durations because it cannot go backwards;
time.time() only for wall-clock timestamps.
"""),

"ref-python-gotchas": ("Python gotchas that bite", "ref, code", """
A mutable default argument is created once, at definition, and shared by every
call. def f(x, acc=[]) accumulates across calls forever. Use None and build
inside.

Late binding in closures: [lambda: i for i in range(3)] gives three functions
that all return 2, because they capture the variable, not its value.

is compares identity, == compares value. It works for small integers and short
strings by accident, because those are interned, and stops working the moment
the values get larger.

Integer division // floors toward negative infinity, so -7 // 2 is -4, not -3.
And % follows it, so -7 % 2 is 1.

dict preserves insertion order since 3.7, and that is a language guarantee now,
not an implementation detail.

Modifying a list while iterating it skips elements. Iterate over a copy.

except Exception does not catch KeyboardInterrupt or SystemExit, which is
usually what you want; a bare except: does, which is usually not.

f-strings cannot contain a backslash inside the expression part before 3.12, and
nesting the same quote character is a syntax error. That is the most common
failure when generating Python inside another string.
"""),

# ----------------------------------------------------------------- practical
"ref-curl": ("curl flags worth memorising", "ref, code", """
-s silent, -S still show errors (use -sS together). -o FILE writes to a file, -O
uses the remote name. -L follows redirects, which curl does NOT do by default.
-i includes response headers, -I sends HEAD only.

-X METHOD, -H "Header: value" repeatable, -d 'body' which implies POST, --data-urlencode
for query parameters that need escaping, -F for multipart uploads including
-F file=@path.

-m SECONDS is a total timeout and --connect-timeout bounds only the handshake.
Without -m, a hung server hangs your script forever.

-w '%{http_code}' prints just the status, which combined with -o /dev/null is the
cleanest way to assert on a response in a script. Other useful ones:
%{time_total}, %{size_download}, %{url_effective}.

-N disables buffering, which is required to watch a server-sent-events stream
arrive rather than receiving it in one lump at the end.

-k skips certificate verification and should be a deliberate decision, not a
habit.
"""),

"ref-units": ("Unit conversions worth knowing", "ref, sci", """
Length: 1 inch 25.4 mm exactly. 1 foot 0.3048 m. 1 yard 0.9144 m. 1 mile
1.609344 km. 1 nautical mile 1852 m exactly.

Mass: 1 pound 0.45359237 kg exactly. 1 ounce 28.3495 g. 1 stone 6.35029 kg.
1 tonne 1000 kg; 1 US ton 907.185 kg; 1 UK long ton 1016.05 kg.

Volume: 1 litre 1000 cm3. 1 UK pint 568.261 ml, 1 US pint 473.176 ml — a fifth
smaller, which is why recipes go wrong. 1 UK gallon 4.54609 l, 1 US gallon
3.78541 l.

Temperature: C to F is x9/5 then +32. F to C is -32 then x5/9. -40 is the same
in both. K is C + 273.15.

Pressure: 1 bar 100 kPa, 1 atm 101.325 kPa, 1 psi 6.89476 kPa.

Energy: 1 calorie 4.184 J. 1 kWh 3.6 MJ. A dietary Calorie is a kilocalorie.

Speed: 1 mph 1.60934 km/h. 1 knot 1.852 km/h. 1 m/s 3.6 km/h.

Useful approximations: a litre of water is a kilogram. 10 mph is about 4.5 m/s.
A metre is a long stride.
"""),

"ref-markdown": ("Markdown and YAML syntax", "ref, code", """
Markdown: # through ###### for headings. **bold**, *italic*, `code`, ```fenced
blocks``` with an optional language. - or * for bullets, 1. for numbered.
> blockquote. [text](url) for links, and an image is the same with a leading !.
A table needs a header row and a |---|---| separator. Two trailing spaces or a
backslash force a line break; a single newline does not.

Obsidian adds wikilinks, written as `[[name]]`, which resolve against the FILE
NAME rather than the note title; `[[name|display text]]` shows something else.
Backticks matter here: an unfenced example of the syntax IS a link, and this
note previously contained two broken ones for exactly that reason. Links inside
a fenced code block are not parsed.

YAML: two-space indentation, never tabs — a tab is a parse error. key: value.
Lists as - item. Nested structures by indentation.

The traps: unquoted yes, no, on, off, true and false all become booleans, which
is why country code NO becomes False. A bare number with a leading zero may be
read as octal. A colon followed by a space inside an unquoted value ends the key.
Version numbers like 1.10 become floats and lose the trailing zero.

Quote anything that might be ambiguous. Multi-line strings: | keeps newlines,
> folds them into spaces.
"""),
}


def main():
    for old in MEM.glob("ref-*.md"):
        old.unlink()

    for stem, (title, tags, body) in NOTES.items():
        doc = ("---\n"
               f"created: {NOW}\n"
               f"title: {title}\n"
               f"tags: [{tags}, reference]\n"
               "source: hand-written reference\n"
               "---\n\n"
               f"# {title}\n\n{body.strip()}\n")
        (MEM / f"{stem}.md").write_text(doc, encoding="utf-8")

    print(f"  reference notes written: {len(NOTES)}")


main()
