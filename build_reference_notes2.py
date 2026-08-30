"""A second batch of reference notes: the working knowledge, not the article.

The first batch proved the format. This extends it into the things this
particular user actually does — a homelab, 3D printing, electronics, code — and
into the kitchen, where an encyclopedia is at its least useful. Wikipedia has a
long article on rice. It will not tell you the ratio.

Same rules as the first batch. Written rather than fetched, because these are
stable facts and a scraped cheatsheet is a worse cheatsheet. Built as compact
tables, because retrieval returns a 900-character window and prose does not
survive that. And anything version-dependent or that I am not certain of is
left out: a reference note that is wrong is worse than one that is missing,
since a wrong one is consulted with confidence.
"""
import datetime
import pathlib

MEM = pathlib.Path("/opt/orb/mem")
NOW = datetime.datetime.now().isoformat(timespec="seconds")

NOTES = {
# --------------------------------------------------------------- command line
"ref2-find-grep-sed": ("find, grep, sed and awk", "ref, code", """
find . -name "*.py" by name, -iname case-insensitively, -type f files or d
directories, -size +100M, -mtime -7 modified in the last week, -maxdepth 2.
-exec cmd {} \\; runs once per file; -exec cmd {} + batches them, which is much
faster. -delete instead of -exec rm. -xdev stays on one filesystem, which
matters when /proc and network mounts are about.

grep -r recursive, -i case-insensitive, -n line numbers, -v invert, -l names
only, -c count, -o only the match, -A/-B/-C lines after, before, around.
-E extended regex, -F fixed string (much faster, and safe when the pattern
contains dots or brackets). The bracket trick, grep "[p]ython", stops the grep
process matching itself in ps output.

sed 's/old/new/' first per line, 's/old/new/g' all, -i edits in place, -n with
p prints only matches, and the delimiter can be anything: s|/a/b|/c/d| avoids
escaping slashes.

awk '{print $3}' a column, -F, sets the separator, 'NR==2' a line by number,
'$3 > 100' a condition, '{s+=$1} END {print s}' a running total.

Word of warning: parsing ls output breaks on spaces. Use find -print0 with
xargs -0.
"""),

"ref2-tar-rsync-ssh": ("tar, rsync and ssh", "ref, ops", """
tar czf out.tgz dir creates gzipped, xzf extracts, tzf lists without extracting.
The order c/x/t matters and f must come last before the filename. -C dir changes
directory first, which is how you avoid absolute paths in the archive.
tar czf - dir streams to stdout, which is how you pipe an archive out of a
container without writing it inside.

Always list before extracting something you did not make: an archive can contain
absolute paths or ../ and scatter files across the filesystem.

rsync -a archive mode (recursive, permissions, times, symlinks), -v verbose,
-z compress in transit, -P progress and resume, --delete removes files at the
destination that are gone from the source, -n dry run. Always dry-run --delete
first.

The trailing slash is the classic mistake. rsync src/ dst copies the CONTENTS of
src into dst; rsync src dst copies the directory itself into dst, creating
dst/src.

ssh -i key, -p port, -L 8080:localhost:80 forwards a local port to the remote
side, -R does the reverse, -N no command (just the tunnel), -f background.
ssh-copy-id installs your public key. ~/.ssh/config with Host, HostName, User,
IdentityFile and Port turns all of that into one word.

A private key must be mode 600 or ssh refuses it outright.
"""),

"ref2-network-debug": ("Network troubleshooting commands", "ref, ops", """
Work up the stack, because the answer is almost always lower than you think.

Is the machine there: ping host. Note that many hosts drop ICMP and a failed
ping proves less than people assume.

Where does it stop: traceroute host, or mtr for a continuous view.

Does the name resolve: dig name, dig +short name for just the answer,
dig @1.1.1.1 name to bypass your resolver, dig -x IP for reverse. If dig
succeeds and the application fails, the problem is the application's resolver
config, not DNS.

Is the port open: ss -tlnp lists listening TCP sockets with the process,
ss -tnp shows established connections. netstat is the older equivalent.
nc -zv host port tests one port from here.

What is actually on the wire: tcpdump -i any -n port 443, and -w file.pcap to
open in Wireshark later.

What is the service saying: curl -v shows the handshake and headers,
curl -w '%{http_code}' just the status.

Inside Docker, containers resolve each other by SERVICE NAME on the same
network, and not at all across networks. A name that does not resolve is
usually two containers on different networks rather than a DNS fault.
"""),

"ref2-dns-records": ("DNS record types", "ref, cs", """
A maps a name to an IPv4 address. AAAA to IPv6. CNAME aliases one name to
another and cannot coexist with other records at the same name, which is why it
cannot be used at a zone apex.

MX for mail, with a priority number where lower is preferred. TXT for arbitrary
text, which is where SPF, DKIM and domain-verification records live. NS
delegates a zone to nameservers. SOA holds the zone's serial and timers. PTR is
the reverse lookup, and lives under in-addr.arpa. SRV advertises a service with
priority, weight, port and target. CAA restricts which certificate authorities
may issue for the domain.

TTL is how long resolvers may cache an answer. Lower it BEFORE a migration, not
during: the old TTL governs how long the stale answer survives, so dropping it
on the day changes nothing for anyone who already asked.

Negative answers are cached too, governed by the SOA minimum. A record that did
not exist five minutes ago can keep not existing for a while after you create
it, which is the usual explanation for "it works for you but not for me".
"""),

"ref2-tls": ("TLS and HTTPS certificates: expiry, chains and trust errors", "ref, security", """
A certificate binds a public key to a name, signed by an authority the client
already trusts. The private key never leaves the server.

Inspect a live one: openssl s_client -connect host:443 -servername host, and
the servername matters because virtual hosts serve different certificates on the
same address. Inspect a file: openssl x509 -in cert.pem -noout -text, or
-noout -dates for just validity.

Common failures, in order of likelihood. Name mismatch: the certificate does not
cover the name used, and a wildcard covers one level only, so *.example.com does
not match a.b.example.com. Expired, which is why automated renewal exists.
Incomplete chain: the server must send its intermediates, and a browser that
works while curl fails is nearly always this, because browsers cache
intermediates and curl does not. Clock skew on the client. Self-signed, which is
not trusted by anything without explicit installation.

Let's Encrypt certificates last 90 days and are meant to be renewed
automatically at 60. Renewal needs port 80 reachable for the HTTP challenge, or
DNS access for the DNS challenge, which is the only option for a wildcard.
"""),

"ref2-jq": ("jq: extracting fields and parsing JSON on the command line", "ref, code", """
jq '.' pretty-prints. jq -r removes the quotes from string output, which is what
you want when feeding a shell variable. jq -c compact, one line per result.

jq '.key' one field, '.a.b.c' nested, '.[0]' an array element, '.[]' every
element as a separate result, '.items[]' the elements of a field.

Selecting: jq '.[] | select(.age > 30)', and select on a string is
'select(.name == "x")'. Extracting several fields: jq '.[] | {name, age}'.
Renaming: jq '{n: .name}'.

Piping inside jq is not the shell pipe: '.items[] | .name' passes each result on.

Useful: 'length', 'keys', 'has("x")', 'map(.x)', 'add' to sum, 'group_by(.k)',
'sort_by(.k)', 'unique', 'join(",")', 'tostring', 'tonumber',
'// "default"' for a fallback when a key is missing or null.

jq -e sets a non-zero exit code when the result is null or false, which is how
you test a JSON response in a script.

Reading a field that does not exist returns null rather than failing, so a typo
in a path is silent — check with 'keys' when a filter mysteriously returns
nothing.
"""),

# ------------------------------------------------------------------ data & web
"ref2-sql-joins": ("SQL joins and query order", "ref, cs", """
INNER JOIN keeps rows matching on both sides. LEFT JOIN keeps every row from the
left and fills the right with NULL where there is no match. RIGHT JOIN is the
mirror and is rarely used, because swapping the tables is clearer. FULL OUTER
keeps everything. CROSS JOIN is every combination, and is what you get by
accident when the ON clause is missing.

The trap with LEFT JOIN: putting a condition on the right table in WHERE turns it
back into an INNER JOIN, because NULL fails the comparison. Conditions on the
right table belong in the ON clause.

Logical evaluation order is not the written order: FROM and JOIN, then WHERE,
then GROUP BY, then HAVING, then SELECT, then ORDER BY, then LIMIT. That is why
you cannot use a SELECT alias in WHERE but can in ORDER BY, and why WHERE filters
rows while HAVING filters groups.

COUNT(*) counts rows; COUNT(col) skips NULLs. Any comparison with NULL is
unknown, so use IS NULL, and NOT IN with a NULL in the list returns nothing at
all — a genuinely nasty silent failure.

An index helps a WHERE, a JOIN key and an ORDER BY. Wrapping the column in a
function usually prevents its use: WHERE date(created) = ... cannot use an index
on created.
"""),

"ref2-css-layout": ("CSS flexbox and grid, and centering a div", "ref, code", """
Flexbox is one dimension, grid is two. That single sentence resolves most of the
choice.

Flex: display:flex, flex-direction row or column, justify-content along the main
axis, align-items across it. gap for spacing, in preference to margins. flex:1
makes a child take the remaining space; flex-wrap:wrap lets them onto new lines.

The one everyone hits: justify-content and align-items swap meaning when
flex-direction is column, because they are defined relative to the main axis and
not to the screen.

Grid: display:grid, grid-template-columns repeat(3, 1fr) for three equal
columns, or repeat(auto-fit, minmax(200px, 1fr)) for a responsive set with no
media query at all. grid-column: span 2 to make a child wider. place-items
centres in both directions in one line.

Centring: display:grid with place-items:center is the shortest reliable answer.

position:absolute is relative to the nearest positioned ancestor, so the parent
needs position:relative. transform, filter and will-change each create a new
containing block, which is why a fixed element sometimes stops being fixed
inside an animated parent.

Animate only transform and opacity. Anything else — width, top, filter — forces
layout or paint on every frame.
"""),

"ref2-datetime": ("Date and time formats: ISO 8601, strftime and Unix time", "ref, code", """
ISO 8601 is the only format worth writing: 2026-08-30, or 2026-08-30T14:05:00Z
with time. Z means UTC; an offset is written +01:00. It sorts correctly as text,
which no other format does.

strftime codes: %Y four-digit year, %m month, %d day, %H hour 24, %M minute, %S
second, %j day of year, %A weekday name, %B month name, %z offset, %s Unix
seconds. %-d and %-m drop the leading zero on Linux but not everywhere.

Unix time is seconds since 1970-01-01 UTC, and has no timezone by definition.
Milliseconds are common in JavaScript and a frequent source of off-by-1000.

Store UTC, display local. Storing local time loses the offset and the hour that
repeats when clocks go back is then genuinely ambiguous.

Durations should use a monotonic clock, not wall time: wall time can jump
backwards when NTP corrects it, and a negative duration is the result.

Week numbers are a trap. ISO weeks start on Monday and week 1 is the one
containing the first Thursday, so early January can be week 52 of the previous
year.
"""),

# ------------------------------------------------------------------- homelab
"ref2-proxmox-lxc": ("Proxmox and LXC commands", "ref, ops", """
pct list shows containers. pct start, stop, reboot, shutdown by ID.
pct enter ID opens a shell; pct exec ID -- cmd runs one command without one.
pct push ID local remote and pct pull copy files across the boundary.
pct config ID shows the configuration; pct set ID -memory 6144 changes it, and
memory can be changed live.

pct resize ID rootfs +10G grows the disk, online, and resizes the filesystem for
you. It cannot shrink.

qm is the same set of verbs for full VMs rather than containers.

Snapshots: pct snapshot ID name, pct rollback ID name, pct listsnapshot ID.
Backups: vzdump ID --storage local --mode snapshot.

pveam update then pveam available lists container templates.

The one that catches people: pct lives in /usr/sbin, and a root user crontab
runs with PATH=/usr/bin:/bin, which does NOT inherit the PATH from
/etc/crontab. A backup script calling pct from cron silently finds nothing.
Set PATH in the script or call it by absolute path.
"""),

"ref2-vim-tmux": ("vim and tmux survival", "ref, code", """
vim, enough to get out and edit a config. i insert, Esc back to normal, :w write,
:q quit, :wq both, :q! quit discarding. dd delete a line, yy copy, p paste, u
undo, Ctrl-r redo. gg top, G bottom, :42 line 42. /text search, n next, N
previous. :%s/old/new/g replace throughout, add c to confirm each. v visual, V
by line, then d or y. :set paste before pasting into a terminal, or autoindent
turns it into a staircase.

tmux, for anything long-running over ssh. tmux new -s name starts a session,
tmux a -t name reattaches, tmux ls lists. The prefix is Ctrl-b: prefix d
detaches, prefix c new window, prefix n and p to move between them, prefix %
splits vertically, prefix " horizontally, prefix arrow moves between panes,
prefix z zooms a pane full screen and back, prefix [ enters scroll mode (q to
leave).

The reason to bother: a session survives the ssh connection dropping. A long
build or a model download that dies with your laptop lid is the alternative.
"""),

"ref2-python-packaging": ("Python virtual environments (venv), pip and packaging", "ref, code", """
python -m venv .venv creates an environment, source .venv/bin/activate enters
it, deactivate leaves. The point is that dependencies belong to a project rather
than the system, and a system Python broken by pip install is genuinely
unpleasant to repair.

pip install -r requirements.txt, pip freeze > requirements.txt to record exactly
what is installed. pip install -e . for a local package in editable mode.

uv is the modern replacement and is dramatically faster: uv venv, uv pip install,
uv run script.py, uv sync from a lockfile. It resolves in seconds where pip
takes minutes.

pyproject.toml is the current standard. [project] holds name, version,
dependencies; [build-system] names the backend. setup.py is legacy.

python -m module runs a module as a script, which is how you get the right
interpreter rather than whatever is first on PATH — python -m pip beats pip for
exactly that reason.

PYTHONPATH is a last resort. If imports only work from one directory, the layout
is wrong rather than the path.
"""),

# ---------------------------------------------------------------- making
"ref2-resistors": ("Resistor colour codes and component values", "ref, make", """
Colour to digit: black 0, brown 1, red 2, orange 3, yellow 4, green 5, blue 6,
violet 7, grey 8, white 9. Worth memorising once and never looking up again.

Four bands: two digits, a multiplier, then tolerance. Five bands: three digits, a
multiplier, then tolerance. The multiplier uses the same colours as powers of
ten; gold is x0.1 and silver x0.01.

Tolerance band: brown 1%, red 2%, gold 5%, silver 10%, none 20%. Gold or silver
is always the tolerance, which tells you which end to read from.

So brown-black-red-gold is 1, 0, x100, 5% — 1 kilohm.

Capacitors are marked differently. A three-digit code is two digits and a
multiplier in picofarads, so 104 is 10 followed by four zeros, 100000 pF, which
is 100 nF or 0.1 uF — the commonest decoupling capacitor there is.

E12 is the standard series and explains the odd-looking values: 10, 12, 15, 18,
22, 27, 33, 39, 47, 56, 68, 82 and their decades. If a calculation gives 3.7k,
the part you can buy is 3.9k.

Ohm's law V = IR, and power P = VI = I2R. A resistor's wattage rating matters:
dropping 5 V at 20 mA is 0.1 W, which is fine for a quarter-watt part and not
for anything smaller.
"""),

"ref2-3d-printing": ("3D printing settings and faults", "ref, make", """
Temperatures, nozzle then bed. PLA 190-220 and 50-60, and it prints on almost
anything. PETG 230-250 and 70-85, stringy and tougher. ABS 230-250 and 100-110,
and it needs an enclosure or it will warp and split. TPU 220-235, printed slowly
at 20-30 mm/s with as direct a filament path as possible.

Layer height with a 0.4 mm nozzle: 0.2 is the sensible default, 0.12-0.16 for
detail, 0.28-0.3 for speed. Below about a quarter of the nozzle diameter gains
nothing. First layer thicker and slower than the rest.

Faults and their usual causes. Not sticking: nozzle too high, bed dirty, or too
cool. Stringing: retraction too short, temperature too high, travel too slow —
PETG strings whatever you do. Warping and lifting corners: cooling too fast or
no brim, and with ABS it means no enclosure. Layer shifting: belt tension or
printing too fast. Gaps in the top surface: too few top layers or under
extrusion. Elephant's foot on the first layer: nozzle too low or bed too hot.

Perimeters matter more than infill for strength. Three or four walls with 15%
infill beats two walls with 50%, uses less filament, and prints faster.

Print orientation decides strength: layers separate under load along the Z axis,
so lay a part so that force acts across the layers rather than trying to peel
them apart.
"""),

# --------------------------------------------------------------------- kitchen
"ref2-cooking-ratios": ("Cooking ratios and temperatures: rice, pasta, bread, meat", "ref, kitchen", """
Rice, by volume: long grain 1 part rice to 2 water, basmati 1 to 1.5 after
rinsing, brown 1 to 2.5 and about 40 minutes. Bring to the boil, cover, lowest
heat, then rest off the heat for 10 minutes without lifting the lid.

Pasta: a litre of water and 10 g salt per 100 g pasta. Reserve a cup of the
starchy water before draining — it is what makes a sauce cling.

Bread, in baker's percentages against flour weight: 60-70% water, 2% salt, 1%
instant yeast. Higher hydration gives an open crumb and a stickier dough.

Eggs from boiling water, large: 6 minutes soft, 7-8 jammy, 9-10 hard. Straight
into cold water to stop it and to make peeling possible.

Meat internal temperatures: chicken 74C throughout. Beef 52 rare, 57 medium
rare, 63 medium. Pork 63 and rested. Rest large joints 10-20 minutes; carrying
over adds a few degrees.

Roasting: 200C for vegetables and for crisp skin, 160-180C for anything slow.
Do not crowd the tray — steam is the enemy of browning.

Substitutions: 1 tsp baking powder is a quarter tsp bicarbonate of soda plus
half a tsp cream of tartar. Buttermilk is a tablespoon of lemon juice in a cup of
milk, left 10 minutes. A teaspoon is 5 ml, a tablespoon 15 ml, a UK cup 250 ml.

Salt: season in layers throughout, not at the end. It is the one correction you
cannot make backwards.
"""),
}


def main():
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
