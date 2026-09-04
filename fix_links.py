"""Repair wikilinks so Obsidian can resolve them.

The vault was generated with links written as prose — [[operating system]] —
while the files were saved as slugs, operating-system.md. Obsidian resolves a
wikilink against the FILE NAME, so 1308 of 2073 links pointed at nothing. The
practical effect is that the graph was mostly ghost nodes: the notes were
cross-referenced in the text and unconnected in the data.

Rewriting to [[operating-system|operating system]] fixes the edge while keeping
the sentence readable — the alias after the pipe is what the reader sees, so no
note's prose changes at all.

Runs in place over the vault. Idempotent: a link that already resolves is left
untouched, so this can be re-run after new notes are ingested.
"""
import pathlib
import re
import sys

import vaultpaths

VAULT = pathlib.Path("/opt/orb/mem")

# Three links were generated with a nested opening bracket —
# "[[message [[authentication]] code]]" — which is not a link at all, just
# broken text. The inner pair is stripped, then the result is mapped by hand
# because the slug it produces is a genuine near-miss for the real note.
MANUAL = {
    "message authentication": "message-authentication-code",
}

LINK = re.compile(r"\[\[([^\[\]]+?)\]\]")
NESTED = re.compile(r"\[\[([^\[\]]*?)\[\[")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    # Walked once and reused. Obsidian resolves a wikilink by basename
    # regardless of folder, so the link targets are exactly the same set they
    # were before the vault was sorted - but a top-level glob now finds four
    # files, which would report every link in the vault as broken and then
    # "fix" them into something worse.
    all_notes = sorted(vaultpaths.notes(VAULT))
    stems = {p.stem for p in all_notes}
    by_lower = {s.lower(): s for s in stems}

    # Some notes are filed under a prefix that the prose never uses: the note
    # titled "Dehydration" is field-dehydration.md, and "Orb system" is
    # orb-overview.md. Slugging the link text can never reach those, so the
    # frontmatter title is the authority and is checked before giving up.
    by_title = {}
    for p in all_notes:
        head = p.read_text(encoding="utf-8", errors="replace")[:400]
        m = re.search(r"^title:\s*(.+)$", head, re.M)
        if m:
            by_title.setdefault(m.group(1).strip().lower(), p.stem)

    fixed = touched = already = unresolved = 0
    misses = {}

    for path in all_notes:
        raw = original = path.read_text(encoding="utf-8", errors="replace")

        # Collapse the nested-bracket damage before anything tries to parse it.
        while NESTED.search(raw):
            raw = NESTED.sub(r"[[\1", raw, count=1)

        def repl(m):
            nonlocal fixed, already, unresolved
            inner = m.group(1)
            target, _, alias = inner.partition("|")
            target = target.strip()
            alias = alias.strip()

            if target in stems:                       # already correct
                already += 1
                return m.group(0)

            candidate = (by_lower.get(target.lower())
                         or by_title.get(target.lower())
                         or MANUAL.get(target.lower())
                         or (slug(target) if slug(target) in stems else None))

            if not candidate:
                unresolved += 1
                misses[target] = misses.get(target, 0) + 1
                return m.group(0)

            fixed += 1
            # The display text is preserved exactly as the sentence had it, so
            # repairing the link never rewrites the prose around it.
            return f"[[{candidate}|{alias or target}]]"

        raw = LINK.sub(repl, raw)

        if raw != original:
            path.write_text(raw, encoding="utf-8")
            touched += 1

    print(f"  notes rewritten      : {touched}")
    print(f"  links repaired       : {fixed}")
    print(f"  already resolving    : {already}")
    print(f"  still unresolved     : {unresolved}")
    if misses:
        print("  remaining ghost targets (these become empty nodes):")
        for k, v in sorted(misses.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {v:3}x  [[{k}]]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
