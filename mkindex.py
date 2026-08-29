"""Regenerate the vault index from what is actually on disk.

The first index was hand-written and immediately started lying: it linked to
eight notes that had not been created yet. An index that is generated cannot
drift from the vault it describes.
"""
import datetime, pathlib, re

MEM = pathlib.Path("/opt/orb/mem")

# Test artefacts from building the upload path.
for junk in list(MEM.glob("threat-model*.md")) + list(MEM.glob("y-*.md")) \
          + list(MEM.glob("zarquon*.md")):
    junk.unlink()
    print(f"  removed {junk.name}")

by_tag, facts = {}, 0
for p in sorted(MEM.glob("*.md")):
    if p.name == "index.md":
        continue
    raw = p.read_text(encoding="utf-8", errors="replace")
    fm = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", raw, re.S)
    head = fm.group(1) if fm else ""
    body = raw[fm.end():] if fm else raw
    t = re.search(r"^title:\s*(.+)$", head, re.M)
    h = re.search(r"^#\s+(.+)$", body, re.M)
    title = (t.group(1) if t else (h.group(1) if h else p.stem)).strip()
    tag = "note"
    tg = re.search(r"^tags:\s*\[([^\]]*)\]", head, re.M)
    if tg:
        tag = tg.group(1).split(",")[0].strip() or "note"
    stripped = re.sub(r"^#\s+.+$", "", body, count=1, flags=re.M).strip()
    if len(stripped) <= 240:
        facts += 1
        continue
    by_tag.setdefault(tag, []).append(title)

LABEL = {"ai": "Artificial intelligence and machine learning",
         "security": "Security", "cs": "Computer science and systems",
         "field": "Field medicine and navigation", "orb": "Orb, the device itself",
         "uploaded": "Uploaded documents", "note": "Other"}
ORDER = ["orb", "ai", "security", "cs", "field", "uploaded", "note"]

total = sum(len(v) for v in by_tag.values())
parts = [
    f"This vault holds {total} notes plus {facts} standing facts. Everything below is "
    "searchable by the assistant and editable in Obsidian from any device; the two are "
    "the same directory.\n",
    "Notes were built from the offline Wikipedia carried on the device, so what the "
    "assistant tells you and what it can show you cannot drift apart. Field notes are "
    "hand-written and lead with what to do, because the archive already holds the "
    "definitional version.\n",
]
for tag in ORDER:
    names = sorted(by_tag.get(tag, []))
    if not names:
        continue
    parts.append(f"## {LABEL.get(tag, tag)} ({len(names)})\n")
    parts.append(", ".join(f"[[{n}]]" for n in names) + "\n")

doc = ("---\n"
       f"created: {datetime.datetime.now().isoformat(timespec='seconds')}\n"
       "title: Index\ntags: [orb, moc]\n---\n\n# Index\n\n" + "\n".join(parts))
(MEM / "index.md").write_text(doc, encoding="utf-8")
print(f"  index rebuilt: {total} notes, {facts} facts, {len(by_tag)} sections")
for tag in ORDER:
    if by_tag.get(tag):
        print(f"    {tag:9} {len(by_tag[tag])}")
