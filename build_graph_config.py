"""Write Obsidian's graph view configuration into the vault.

Graph view has no manual layout — it is a force simulation — so everything that
organises it lives in this one file: colour groups, the filter query, and the
force constants. Writing it here rather than tapping it in on a phone means the
same view appears on every device that syncs the vault's config directory.

Colours are stored by Obsidian as a single integer, not a hex string, so they
are converted rather than written literally.
"""
import json
import pathlib

VAULT = pathlib.Path("/opt/orb/mem")
CFG = VAULT / ".obsidian"


def rgb(h):
    return {"a": 1, "rgb": int(h, 16)}


# Order is deliberate. Hub notes carry BOTH #moc and their domain tag, so
# whichever group Obsidian resolves first decides their colour — #moc leads so
# the 28-note skeleton stays visible as a structure rather than dissolving into
# the cluster it organises.
#
# #reference is deliberately absent: it is on 298 of 338 notes, so as a colour
# group it marks almost everything and distinguishes nothing.
GROUPS = [
    ("tag:#moc",      "FFFFFF"),   # the 28 hubs — index, domains, topics
    ("tag:#security", "E05252"),   # 115
    ("tag:#ai",       "4D9DE0"),   # 91
    ("tag:#cs",       "5FBF77"),   # 66
    ("tag:#field",    "E0A44D"),   # 28
    ("tag:#orb",      "B07FE0"),   # 6
]

graph = {
    "collapse-filter": False,
    "search": "",
    "showTags": False,          # tag nodes would add 14 hubs nobody navigates by
    "showAttachments": False,
    "hideUnresolved": True,     # nothing to hide now, but keeps it that way
    "showOrphans": True,

    "collapse-color-groups": False,
    "colorGroups": [{"query": q, "color": rgb(c)} for q, c in GROUPS],

    "collapse-display": False,
    "showArrow": False,
    # Labels only resolve as you zoom, otherwise 338 captions overlap into noise.
    "textFadeMultiplier": -1.4,
    "nodeSizeMultiplier": 1.15,
    "lineSizeMultiplier": 0.7,

    # Near the extremes, not merely off the defaults. At 338 nodes and ~2250
    # links the defaults collapse the graph into a single ball regardless of
    # how well structured the links are — the hub layer is present in the data
    # and simply cannot be seen. A first pass at 0.28/16/0.55/220 was still a
    # ball on the device; centre strength is the term doing the damage, so it
    # goes to the floor and repulsion to the ceiling.
    "collapse-forces": False,
    "centerStrength": 0.1,
    "repelStrength": 20,
    "linkStrength": 0.3,
    "linkDistance": 400,

    "scale": 0.62,
    "close": False,
}

# Depth 2 is the readable unit on a phone: a note, its neighbours, and the hub
# it hangs from — roughly 20 nodes instead of 338.
local_graph = dict(graph)
local_graph.update({"localJumps": 2, "localBacklinks": True,
                    "localForelinks": True, "localInterlinks": False,
                    "scale": 1.0})

CFG.mkdir(parents=True, exist_ok=True)
(CFG / "graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")

appearance = CFG / "app.json"
if not appearance.exists():
    appearance.write_text(json.dumps({"attachmentFolderPath": "attachments"},
                                     indent=2), encoding="utf-8")

print(f"  wrote {CFG / 'graph.json'}")
print(f"  colour groups: {len(GROUPS)}")
for q, c in GROUPS:
    print(f"    {q:16} #{c}")
print(f"  local graph depth: {local_graph['localJumps']}")
