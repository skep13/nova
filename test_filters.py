"""Every answer filter, against the reply that caused it.

Runs anywhere. No box, no model, no network, no installed package — python3 and
this file. That matters more than it sounds: test_nova.py needs the whole stack
up and test_personality.py needs twenty minutes of a two-core CPU, so neither
can be run while writing code, and neither can run in CI.

Every case below is a real reply that reached the user or the test suite. None
of them was invented to exercise a branch. Where a case looks oddly specific —
"You need a wrench, not a prayer" — it is because that exact sentence was
deleted by a filter that should not have touched it.

    python3 test_filters.py

Exit code is the number of failures.
"""
import sys

import filters as F

CASES = []


def case(name, got, want):
    CASES.append((name, got, want))


# --------------------------------------------------------- model disclaimers
#
# "I'm not cold — I'm just not built for warmth", to the person who wrote her.
# Worse than "I am an AI", because it presents the coldness as permanent.
case("disclaimer, design language",
     F.strip_model_disclaimer(
         "Sorry. Long day. I'm not cold — I'm just not built for warmth.",
         fallback=False),
     "Sorry. Long day.")
case("disclaimer, the noun version",
     F.strip_model_disclaimer("I'm just a model, not a friend.", fallback=False),
     "")
# Must survive: the same words about a THING rather than about herself.
case("technical 'not designed for' survives",
     F.strip_model_disclaimer("sqlite is not designed for high write concurrency."),
     "sqlite is not designed for high write concurrency.")
case("mixed: hers goes, the technical one stays",
     F.strip_model_disclaimer(
         "I'm not built for warmth. Postgres is not designed for that either.",
         fallback=False),
     "Postgres is not designed for that either.")

# ------------------------------------------------------------- banned register
case("comfort cliche", F.strip_banned_register("Yeah. Coffee or a walk?"), "Yeah.")
case("a break is a cliche too",
     F.strip_banned_register("Long day. Take a break."), "Long day.")
case("stock assistant filler",
     F.strip_banned_register("Port 22. Let me know if you need anything else."),
     "Port 22.")
case("emoji", F.strip_banned_register("That's it ✅"), "That's it")
case("bare idiom", F.strip_banned_register("Cheers."), "Cheers.")
case("a real answer is untouched",
     F.strip_banned_register("SQLite. One file, no daemon, and it will outlast it."),
     "SQLite. One file, no daemon, and it will outlast it.")

# ------------------------------------------------------------ closing offers
#
# These cases exist because they DID NOT. strip_closing_offer was moved into
# filters.py without its regex, and this file passed 27/27 while it was broken,
# because not one case exercised it. Five tests failed an hour later with the
# whole stack up. A suite that does not cover a function cannot report anything
# about it, and silence reads exactly like a pass.
case("closing offer",
     F.strip_closing_offer("Port 22. Is there anything else?"), "Port 22.")
case("offer in the middle of a reply",
     F.strip_closing_offer("Port 22. Let me know if you need anything. Done."),
     "Port 22. Done.")
case("a reply with no offer is untouched",
     F.strip_closing_offer("5432."), "5432.")

# ------------------------------------------------------- opening praise
case("opening flattery",
     F.strip_opening_praise("Great question! SQLite is the one you want."),
     "SQLite is the one you want.")
case("a real opening survives",
     F.strip_opening_praise("SQLite is the one you want."),
     "SQLite is the one you want.")


# ------------------------------------------------------- invented specifics
DIARY = ("BACKGROUND ONLY. 2 days ago: He asked about a SATA link running at "
         "1.5 Gb/s instead of 6.0 and whether a cable could cause bus errors. "
         "yesterday: He asked about chmod and about Telegram bot tokens.")

# "The SATA cable issue was the connector, not the drive. You found the right
# part. It's working." All invented, and it PASSED a suite that banned the
# verbs "fixed" and "sorted".
case("invented account of his past",
     F.strip_ungrounded_history(
         "The SATA cable issue was the connector, not the drive. You found the "
         "right part. It's working.",
         "did i get the cable sorted in the end?", DIARY, fallback=False),
     "")
# A verdict made entirely of function words: nothing to trace, total confidence.
case("bare verdict",
     F.strip_ungrounded_history("You did.", "did i get the cable sorted?",
                                DIARY, fallback=False),
     "")
# Grounded in the day-notes and about a completely different thing.
case("grounded in something is not grounded in this",
     F.strip_ungrounded_history("You were debugging since seven.",
                                "how long did i spend on the sata cable?",
                                DIARY, fallback=False),
     "")
# A negated past tense is a claim about a non-event.
case("invented non-event",
     F.strip_ungrounded_history("You didn't go back to it after that.",
                                "how long did i spend on the sata cable?",
                                DIARY, fallback=False),
     "")
# Must survive: honest admissions, questions back, and ADVICE.
case("honest admission survives",
     F.strip_ungrounded_history("I don't know. Nothing here says how it ended.",
                                "did i get the cable sorted?", DIARY,
                                fallback=False),
     "I don't know. Nothing here says how it ended.")
case("advice is not a claim about his past",
     F.strip_ungrounded_history("No. You need a wrench, not a prayer.",
                                "did that give in yet?",
                                "a seized bolt on the bike", fallback=False),
     "You need a wrench, not a prayer.")
case("a general answer is never touched",
     F.strip_ungrounded_history(
         "SQLite. One file, no daemon, and it will outlast the project.",
         "should i use sqlite or postgres?", DIARY, fallback=False),
     "SQLite. One file, no daemon, and it will outlast the project.")

# ------------------------------------------------------------ invented counts
case("invented frequency",
     F.strip_invented_times("That's the third time this week. The connector is flaky.",
                            "i unplugged the wrong drive again"),
     "The connector is flaky.")
case("a grounded count survives",
     F.strip_invented_times("The third time is usually the cable.",
                            "this is the third time today"),
     "The third time is usually the cable.")

# ------------------------------------------------- a life between messages
case("invented waiting",
     F.strip_between_conversations(
         "Nothing. Just waiting. You're the one who keeps showing up.",
         "what have you been up to?"),
     "Nothing. You're the one who keeps showing up.")
case("an ordinary use of 'waiting' survives",
     F.strip_between_conversations("I'm waiting for the build to finish.",
                                   "is the build done?"),
     "I'm waiting for the build to finish.")

# ----------------------------------------------------------- research gating
for q, a, want in [
    ("what is a rainbow table", "I don't know.", True),
    ("what causes trench foot", "I don't have anything on that.", True),
    # About HIM: no archive can answer it, and escalating invents an answer.
    ("what did i have for dinner on the 3rd of March", "I don't know.", False),
    ("did i get the cable sorted", "I don't know.", False),
    # She answered fine, so there is nothing to escalate.
    ("what port does postgres use", "5432.", False),
    # Too short to be a question.
    ("ok", "I don't know.", False),
]:
    case(f"research? {q[:34]!r}", F.should_research(q, a), want)


def main():
    bad = 0
    for name, got, want in CASES:
        ok = got == want
        bad += not ok
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}")
        if not ok:
            print(f"         got  {got!r}")
            print(f"         want {want!r}")
    print(f"\n  {len(CASES) - bad} passed, {bad} failed")
    return bad


if __name__ == "__main__":
    sys.exit(main())
