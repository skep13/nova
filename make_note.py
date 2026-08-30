"""Write the note Nova said it had already written.

On 2026-08-30 over Telegram, asked to create "nova upgrade ideas" with one
item, Nova replied 'Yes, the note titled "nova upgrade ideas" has been created'
-- and nothing had been. It has no way to write a note; it produced a sentence
describing an action it cannot take, in the same confident register it uses for
things that are true.

Creating it by hand here does not fix that, and is not meant to. It makes the
user's note exist, which is what they asked for. The fabrication is a separate
and more serious problem, addressed in the persona.

Kept as a script rather than done once by hand so the note's provenance is
visible: this is a hand-made file, not something the assistant produced.
"""
import datetime
import pathlib

MEM = pathlib.Path("/opt/orb/mem")
NOW = datetime.datetime.now().isoformat(timespec="seconds")

NOTE = f"""---
created: {NOW}
title: Nova upgrade ideas
tags: [nova, ideas]
---

# Nova upgrade ideas

Things Nova cannot do yet. Asked for over Telegram on 2026-08-30.

- Provide notifications on local weather and temperature at 07:30 every day
"""

path = MEM / "nova-upgrade-ideas.md"
path.write_text(NOTE, encoding="utf-8")
print(f"  wrote {path.name} ({len(NOTE)} bytes)")
