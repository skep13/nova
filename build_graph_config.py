"""Write Obsidian's graph view configuration into the vault.

Graph view has no manual layout — it is a force simulation — so everything that
organises it lives in this one file: colour groups, the filter query, and the
force constants. Writing it here rather than tapping it in on a phone means the
same view appears on every device that syncs the vault's config directory.

Colours are stored by Obsidian as a single integer, not a hex string, so they
are converted rather than written literally.

REWRITTEN for the vault as it is now. The previous version was tuned for 338
notes and the vault holds 1,502; the counts in its comments were four times out
of date and two of its groups (#orb at 6 notes) were invisible at that scale.
Every count below was measured, not remembered.
"""
import json
import pathlib
import sys

VAULT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/orb/mem")
CFG = VAULT / ".obsidian"


def rgb(h):
    return {"a": 1, "rgb": int(h, 16)}


# Order is deliberate: Obsidian gives a node the colour of the FIRST group it
# matches, and most notes carry several tags.
#
# #moc leads so the hub skeleton stays visible as a structure rather than
# dissolving into the cluster it organises. #source is second because a source
# note also carries a domain tag and would otherwise be indistinguishable from
# the subject it implements.
#
# #reference is deliberately absent: it is on 1,055 of 1,502 notes, so as a
# colour group it marks almost everything and distinguishes nothing. Same
# reasoning as when the vault was a quarter the size.
#
# Nine groups, because a legend longer than that is not read. Counts measured
# 2026-09-04.
GROUPS = [
    ("tag:#moc",                                    "FFFFFF"),  # 141 hubs
    ("tag:#source OR tag:#code",                    "8899A6"),  # 221 the machine itself
    ("tag:#security",                               "E05252"),  # 133
    ("tag:#ai",                                     "4D9DE0"),  # 101
    ("tag:#cs OR tag:#web OR tag:#ops",             "5FBF77"),  # 167 computing
    # Safety-critical, and the one group that should be findable at a glance.
    ("tag:#field OR tag:#emergency OR tag:#medical", "E8913A"),  # 51+
    ("tag:#health OR tag:#wellbeing OR tag:#mind",   "D96BA0"),  # 132 the body and the head
    ("tag:#home OR tag:#household OR tag:#kitchen OR tag:#cooking OR tag:#garden OR tag:#diy",
                                                     "C4A24D"),  # 167 domestic
    ("tag:#nova",                                    "B07FE0"),  # 250 this project
]

graph = {
    "collapse-filter": False,
    "search": "",
    "showTags": False,          # tag nodes would add hubs nobody navigates by
    "showAttachments": False,
    "hideUnresolved": True,
    "showOrphans": True,

    "collapse-color-groups": False,
    "colorGroups": [{"query": q, "color": rgb(c)} for q, c in GROUPS],

    "collapse-display": False,
    "showArrow": False,
    # Labels only resolve as you zoom; 1,502 captions overlap into noise.
    # Pushed further negative than the 338-note version needed.
    "textFadeMultiplier": -2.2,
    # Smaller nodes at four times the count, or the graph is solid ink.
    "nodeSizeMultiplier": 0.8,
    "lineSizeMultiplier": 0.5,

    # Near the extremes, not merely off the defaults. The defaults collapse a
    # graph this size into a single ball regardless of how well structured the
    # links are — the hub layer is present in the data and simply cannot be
    # seen. Centre strength is the term doing the damage, so it sits at the
    # floor and repulsion at the ceiling.
    #
    # Raised again from the 338-note settings: four times the nodes need
    # proportionally more room or the clusters merge back into one mass.
    "collapse-forces": False,
    "centerStrength": 0.05,
    "repelStrength": 25,
    "linkStrength": 0.25,
    "linkDistance": 550,

    "scale": 0.35,
    "close": False,
}

# Depth 2 is the readable unit on a phone: a note, its neighbours, and the hub
# it hangs from — roughly 20 nodes instead of 1,502.
local_graph = dict(graph)
local_graph.update({"localJumps": 2, "localBacklinks": True,
                    "localForelinks": True, "localInterlinks": False,
                    "scale": 1.0, "nodeSizeMultiplier": 1.1,
                    "textFadeMultiplier": 0.0})

CFG.mkdir(parents=True, exist_ok=True)
(CFG / "graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
(CFG / "local-graph.json").write_text(json.dumps(local_graph, indent=2),
                                      encoding="utf-8")

print(f"  {len(GROUPS)} colour groups written to {CFG}")
for q, c in GROUPS:
    print(f"    #{c}  {q}")
