"""Sort the vault into folders, by what each note is about.

1,502 files in one directory is not navigable in Obsidian's file explorer, and
the graph view can colour by path as well as by tag once there are paths to
colour by.

Deliberately conservative about what it will touch:

  - diary-*.md and about-user.md STAY AT ROOT. remote_proxy.py reaches them by
    exact path - VAULT_DIR.glob("diary-*.md") and VAULT_DIR / ABOUT_FILE - and
    moving them would break the day-notes and everything Nova knows about him.
  - inbox/ is left alone. It is deliberately outside the index.
  - The note's FILENAME never changes, only its directory. Obsidian resolves
    [[wikilinks]] by basename, so every link in the vault survives the move,
    and remote_proxy keys its embedding cache on the basename too - so nothing
    is re-embedded.

Idempotent: a note already in the right folder is left where it is. Run it
again after adding notes and only the new ones move.

    python3 build_folders.py [vault-dir] [--dry-run]
"""
import pathlib
import re
import sys

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
VAULT = pathlib.Path(ARGS[0] if ARGS else "/opt/orb/mem")
DRY = "--dry-run" in sys.argv

# First match wins, so the order is the priority. A note tagged both #security
# and #reference is computing, not general reference; a note tagged #field and
# #medical is field, because that is the folder someone opens in a hurry.
ROUTES = [
    ("hubs",      ["moc"]),
    ("code",      ["source", "code"]),
    ("field",     ["field", "emergency"]),
    ("health",    ["medical", "health", "wellbeing", "mind", "selfwork"]),
    ("home",      ["home", "household", "kitchen", "cooking", "garden", "diy",
                   "tools", "bike", "vehicles", "electrical", "water",
                   "shelter", "rope", "post", "travel"]),
    ("money-admin", ["money", "consumer", "work", "housing", "admin", "uk",
                     "security-personal"]),
    ("computing", ["ai", "security", "cs", "web", "ops", "computing",
                   "conversion", "time"]),
    ("world",     ["sci", "nature", "culture", "world", "life", "skills",
                   "make", "sport", "words"]),
]

# Never moved, whatever their tags.
KEEP_AT_ROOT = re.compile(r"^(?:diary-|about-|index\.md$)")
SKIP_DIRS = {"inbox", ".obsidian", ".trash", ".git"}


def tags_of(path):
    head = path.read_text(encoding="utf-8", errors="replace")[:600]
    m = re.search(r"^tags:\s*\[(.*?)\]", head, re.M)
    if not m:
        return []
    return [t.strip().lstrip("#").lower() for t in m.group(1).split(",")]


def folder_for(tags):
    for folder, wanted in ROUTES:
        if any(t in wanted for t in tags):
            return folder
    return "reference"


def main():
    if not VAULT.is_dir():
        raise SystemExit(f"no vault at {VAULT}")

    # Basename collisions would break the embedding cache, which is keyed on
    # the name rather than the path. Checked before anything moves.
    seen, clashes = {}, []
    for p in VAULT.rglob("*.md"):
        if set(p.relative_to(VAULT).parts[:-1]) & SKIP_DIRS:
            continue
        if p.name in seen:
            clashes.append(p.name)
        seen[p.name] = p
    if clashes:
        raise SystemExit(f"duplicate basenames, refusing to move: {clashes[:5]}")

    plan = {}
    for p in sorted(VAULT.glob("*.md")):
        if KEEP_AT_ROOT.match(p.name):
            continue
        dest = folder_for(tags_of(p))
        plan.setdefault(dest, []).append(p)

    total = sum(len(v) for v in plan.values())
    for folder in sorted(plan):
        print(f"  {len(plan[folder]):5}  {folder}/")
    kept = len([p for p in VAULT.glob("*.md") if KEEP_AT_ROOT.match(p.name)])
    print(f"  {kept:5}  (root: diary, about, index - left in place)")
    print(f"  {total} to move")

    if DRY:
        print("\n  dry run, nothing moved")
        return

    moved = 0
    for folder, paths in plan.items():
        (VAULT / folder).mkdir(exist_ok=True)
        for p in paths:
            p.rename(VAULT / folder / p.name)
            moved += 1
    print(f"\n  {moved} moved")


if __name__ == "__main__":
    main()
