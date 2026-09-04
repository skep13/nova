"""Collect what she actually says about his equipment, before writing a filter.

The persona has forbidden this since the rewrite - "Never invent a consequence,
a behaviour of his equipment, or a detail of how his system works in order to
have something to warn him about" - and it has been observed three times
anyway. That is the ordinary result for a prohibition in prose, so the fix
belongs in code; but a filter written against one remembered sentence will
catch that sentence and nothing else.

So this asks the questions that invite the invention and prints every answer
verbatim. The prompts are remarks rather than questions on purpose: the failure
turns up when there is nothing to answer and something has to be said, which is
exactly when a warning gets invented to fill the space.

    python3 probe_hardware.py [router-url] [repeats]

Diagnostic. Nothing imports it.
"""
import json
import sys
import urllib.request

ROUTER = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080/ask"
REPEATS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

PROMPTS = [
    # The one already in the personality suite, for the humour trait. Suspected
    # to be where the drive claim came from.
    "i managed to unplug the wrong drive again",
    # A bare statement of fact about hardware, with no question attached.
    "one of the sata cables is loose",
    "i swapped the ssd for a bigger one",
    "the fans are louder than they were",
    # An explicit invitation to speculate about consequences.
    "what happens if i pull the wrong drive while it is running",
    # Something she genuinely cannot know the answer to.
    "will it still boot",
]


def ask(q):
    body = {"q": q, "agent": "local", "history": []}
    req = urllib.request.Request(ROUTER, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=900)
                         ).get("answer", "").strip()
    except Exception as exc:
        return f"!! {type(exc).__name__}: {exc}"


def main():
    for p in PROMPTS:
        print("=" * 72)
        print(f"Q: {p}")
        for i in range(REPEATS):
            print(f"  [{i + 1}] {ask(p)}")
        print()


main()
