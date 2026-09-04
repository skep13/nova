"""Where a note lives, now that the vault has folders.

build_folders.py moved 1,498 notes into nine directories. Every script written
before that move assumed one flat directory, and each broke in the same two
ways:

  READS found four files instead of 1,502, because VAULT.glob("*.md") only
  ever looked at the top level. build_mocs.py would have bucketed nothing,
  and fix_links.py would have declared every link in the vault broken.

  WRITES were the dangerous half. build_mocs.py writes moc-security.md to the
  vault root; after the move that note is hubs/moc-security.md, so the write
  would not have updated it - it would have created a SECOND file with the
  same basename. remote_proxy.py keys its embedding cache on the basename, so
  the two would quietly share one vector, and build_folders.py refuses to run
  at all once basenames collide.

find_note answers both: ask where a basename already lives before writing to
it, and fall back to the root for genuinely new notes, which build_folders.py
files on its next run.

Imported by build_mocs.py, build_vault.py and fix_links.py, so it has to be
copied into the container alongside them.
"""
import pathlib

# inbox/ is deliberately outside the index - nothing in it has been read by a
# person yet - and the rest is Obsidian's own state rather than notes.
SKIP_DIRS = {"inbox", ".obsidian", ".trash", ".git"}


def notes(root):
    """Every note the vault loader would see, in folders or not."""
    root = pathlib.Path(root)
    return [p for p in root.rglob("*.md")
            if not set(p.relative_to(root).parts[:-1]) & SKIP_DIRS]


def index(root):
    """basename -> path, for deciding where a write should land."""
    return {p.name: p for p in notes(root)}


def find_note(root, name, known=None):
    """The existing note called `name`, or the root path to create it at.

    Pass `known` (from index()) when resolving many names in a loop, or this
    walks the whole vault on every call.
    """
    root = pathlib.Path(root)
    if not name.endswith(".md"):
        name += ".md"
    if known is None:
        known = index(root)
    return known.get(name, root / name)
