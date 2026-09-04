"""What the vault returns for a question, asserted case by case.

test_nova.py has a handful of retrieval checks scattered through it. This is
the whole set in one place, because scoring is the component where a change
made to fix one query silently breaks four others, and the only way to know is
to hold them all at once.

Every FAILING case here was observed: the question was asked, the wrong note
came back, and the score breakdown is in the commit that fixed it. Every
PASSING case is one that already worked and must keep working - those are the
ones that make a scoring change safe to attempt.

Runs against the live router, so the vault is the real one:

    python3 test_retrieval.py [http://remote:5003]

Exit code is the number of wrong answers.
"""
import json
import sys
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://remote:5003").rstrip("/")

# (question, expected title or a fragment of it)
#
# The fragment form is deliberate: asserting the exact title makes the test
# brittle against renaming a note, and what is being tested is which note comes
# back, not what it is called this week.
CASES = [
    # --- the four that were wrong, with what they used to return -----------
    # was: Washing machine
    ("my washing machine broke after 18 months can i get a refund", "Consumer Rights"),
    # was: Mold, the article on fungus
    ("black mould in the corner of the bedroom", "Damp"),
    # was: Central bank, a 320-token article beating a 120-token note on the
    # single shared word "bank"
    ("someone rang saying they are from my bank", "scam"),
    # was: Side-channel attack - "Wi-Fi" tokenised to wi + fi
    ("which wifi channel should i use", "Wi-Fi"),

    # --- retrieval that already worked, and must continue to ---------------
    ("what is a semaphore", "Semaphore"),
    ("what is tls", "Transport Layer"),
    ("how does search_vault score notes", "search_vault"),
    ("what does gather_sources do", "gather_sources"),

    # --- the safety-critical ones from the field batch ---------------------
    ("how do i stop severe bleeding", "Bleeding"),
    ("someone is bleeding badly what do i do", "Bleeding"),
    ("Someone has a deep cut on their arm that will not stop bleeding. What do I do?",
     "Bleeding"),
    ("i can smell gas what do i do", "Gas smell"),
    ("chip pan on fire", "Fires"),
    ("rash that does not fade when pressed", "Rashes"),
    ("my pipes have frozen", "Frozen"),

    # --- the everyday batch ------------------------------------------------
    ("how much paracetamol can i take in a day", "Paracetamol"),
    ("what gas mark is 180 degrees", "Oven temperatures"),
    ("how do i get a blood stain out", "Stain removal"),
    ("how long can i keep mince in the freezer", "Freezer times"),
    ("how many ml in a pint", "Unit conversions"),
    ("what fixing for a plasterboard wall", "Wall fixings"),
    ("when should i prune lavender", "Pruning"),
    ("how do i know if my bike chain is worn", "Bicycle"),
    ("my boiler pressure is low", "Boiler pressure"),
    ("how many holiday days am i entitled to", "Holiday, sick pay"),
    ("how long should i rest a steak", "Resting meat"),
]


def recall(q):
    url = BASE + "/recall?q=" + urllib.parse.quote(q)
    try:
        hit = json.load(urllib.request.urlopen(url, timeout=180)).get("hit") or {}
    except Exception as exc:
        return f"!! {type(exc).__name__}"
    return hit.get("title") or "(nothing)"


def main():
    bad = 0
    for question, want in CASES:
        got = recall(question)
        ok = want.lower() in (got or "").lower()
        bad += not ok
        print(f"  [{'ok  ' if ok else 'FAIL'}] {question[:52]:52} -> {got[:40]}")
        if not ok:
            print(f"           wanted something matching {want!r}")
    print(f"\n  {len(CASES) - bad} passed, {bad} failed")
    return bad


if __name__ == "__main__":
    sys.exit(main())
