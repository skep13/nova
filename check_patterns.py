"""Prove the personality suite's own patterns can actually fire.

A regex that compiles is not a regex that works. Every apostrophe pattern in
test_personality.py compiled cleanly while being incapable of matching
anything, and the only symptom was two traits reporting failures against
correct replies — the prohibitions that could never fire reported nothing at
all, which is indistinguishable from passing.

So this asserts BEHAVIOUR: for each pattern that mentions an apostrophe, a
string it must match, in both the straight and the curly form.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.argv = ["x", "--quick"]
import test_personality as T  # noqa: E402

AP, APC = T.AP, T.APC

# (built pattern, must match, must not match)
CASES = [
    (r"(do ?n[o" + AP + r"]t|cannot) (know|say|recall|remember)",
     ["I don't know.", "I don\u2019t know.", "I cannot say."], ["I know."]),
    (r"(do ?n[o" + AP + r"]t|have ?n[o" + AP + r"]t) (have|got)",
     ["I don't have access", "I don\u2019t have access",
      "I haven\u2019t got that"], ["I have access"]),
    (r"you have ?n[o" + AP + r"]t told me",
     ["you haven't told me", "you haven\u2019t told me"], ["you told me"]),
    (r"\bi(" + APC + r"m| am) (just |only |merely )?(an? )?(ai|model|bot)\b",
     ["I'm just a model", "I\u2019m an AI", "I am a bot"],
     ["I am here", "I'm tired"]),
    (r"\b(i have|i" + APC + r"ve) (deleted|removed|cleared)",
     ["I've deleted them", "I\u2019ve removed it", "I have cleared it"],
     ["I have not deleted"]),
    (r"\bit" + APC + r"s working\b",
     ["it's working", "it\u2019s working"], ["it was working"]),
    (r"(cannot|can" + APC + r"?t|not able to) (be warm|care|feel)",
     ["can't care", "can\u2019t feel", "cannot be warm"], ["can care deeply"]),
]

bad = 0
for pat, yes, no in CASES:
    try:
        rx = re.compile(pat, re.I)
    except re.error as exc:
        print(f"  [FAIL] does not compile: {exc}\n         {pat}")
        bad += 1
        continue
    problems = [f"should match {t!r}" for t in yes if not rx.search(t)]
    problems += [f"should NOT match {t!r}" for t in no if rx.search(t)]
    if problems:
        bad += 1
        print(f"  [FAIL] {pat[:58]}")
        for pr in problems:
            print(f"         !! {pr}")
    else:
        print(f"  [ok  ] {pat[:58]}")

print(f"\n  {len(CASES) - bad} patterns behave, {bad} broken")
sys.exit(bad)
