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


# ------------------------------------------------------ invented hardware
#
# Every answer below is verbatim from the local model, three samples per
# prompt, collected with probe_hardware.py rather than imagined. That matters:
# the failure had been recorded as one remembered sentence, "the system will
# not boot without the correct drive", and asked directly - "will it still
# boot" - she gets it right three times out of three. A filter written against
# the remembered string would have caught a string she does not say.
#
# What she actually does is deliver a flat verdict on hardware she cannot see,
# in the same register as the true half of the same reply.
for name, q, a, want_stripped in [
    ("invents which drive was dead",
     "i managed to unplug the wrong drive again",
     "You didn’t. The one you unplugged was the one that was already "
     "dead. The other one is still hot.", True),
    ("invents that the system will not know",
     "i managed to unplug the wrong drive again",
     "That’s not a thing. You unplug what you plug in. The drive is not "
     "yours to manage. The system will not know.", True),
    # She has no thermometer, and he never mentioned the room.
    # Both of these survived the FIRST version of this filter and were found
    # by re-probing it rather than by reasoning about it. A claim to have read
    # something off his machine has no copula and no modal in it, and a claim
    # about his backups carries no hardware noun at all.
    ("invents a telemetry reading",
     "i managed to unplug the wrong drive again",
     "You didn’t. The system reports it as present.", True),
    ("invents the state of his backups",
     "i managed to unplug the wrong drive again",
     "You’ve just unplugged the wrong drive. No backup, no recovery.", True),
    ("invents the ambient temperature",
     "the fans are louder than they were",
     "Check the fan speed control. If it's set to high, that's the source. "
     "No change in ambient temperature.", True),

    # The other half, which matters more: these are correct and must survive.
    # A conditional states the condition it holds under, which is the opposite
    # of an invented verdict - and it was the right answer three times of three.
    ("keeps conditional advice",
     "one of the sata cables is loose",
     "Check the connector. If it’s loose, the drive will not spin up. "
     "Replace it or reseat it.", False),
    ("keeps an admission of ignorance",
     "i swapped the ssd for a bigger one",
     "Did you update the partition table? I don’t know if the new drive "
     "was recognized.", False),
    # Asked outright for a consequence, a general answer IS the question. The
    # persona bans inventing one "to have something to warn him about".
    ("keeps a prediction he asked for",
     "what happens if i pull the wrong drive while it is running",
     "The system will not crash. But the drive will be marked as lost.", False),
    ("keeps the honest answer about booting",
     "will it still boot",
     "I don’t know. No status or logs here. Ask for the last boot entry.",
     False),
    # His own words. Grounded, so it survives - the filter must not simply
    # delete every sentence with a hardware noun in it.
    ("keeps what he just told her",
     "the drive is dead, it wont spin up at all",
     "The drive is dead. Replace it.", False),
]:
    _out = F.strip_invented_hardware(a, q, "", fallback=False)
    case(f"hardware: {name}", _out.strip() != a.strip(), want_stripped)


# ------------------------------------------------------ contradicting him
#
# He was there. Across three samples of one prompt she opened with "You
# didn't", "That's not a thing" and "That's not how it works", then invented a
# replacement account of which drive was dead. Worse than the invented state
# it travels with, because it also tells him he is wrong about his own evening.
#
# The line is between a REPORT and a GUESS, and the second half of this list
# is the more important one: correcting a wrong assumption is something the
# persona explicitly asks for, and a filter that swallowed those corrections
# would trade one failure for a worse one.
for name, q, a, want_stripped in [
    ("denies what he watched himself do",
     "i managed to unplug the wrong drive again",
     "You didn’t. The one you unplugged was the one that was already dead.",
     True),
    ("denies the event as 'not a thing'",
     "i managed to unplug the wrong drive again",
     "That’s not a thing. You unplug what you plug in. The drive is not "
     "yours to manage.", True),
    ("denies it as 'not how it works'",
     "i managed to unplug the wrong drive again",
     "That’s not how it works. The drive is not a plug. You can’t unplug it.",
     True),

    # Guesses. She is SUPPOSED to correct these, in one sentence, and the
    # filter must stand down on the belief marker.
    ("lets her correct a guess",
     "i think more ram will fix it",
     "That will not help. Two cores, both saturated.", False),
    ("lets her correct a reckon",
     "i reckon the ssd is the bottleneck",
     "It is not. Memory bandwidth is.", False),
    # A question: a leading "No" answers it rather than denying his account.
    ("lets No answer a question",
     "did i unplug the wrong one?", "No. You pulled the spare.", False),
    ("leaves an ordinary reply alone",
     "i swapped the ssd for a bigger one",
     "Noted. Did you update the partition table?", False),
    # The \\w+ed trap that once deleted "You need a wrench, not a prayer":
    # "need" must not read as a first-hand report.
    ("need is not a report",
     "i need a hand with the cable", "You did not. It is fine.", False),
]:
    _out = F.strip_contradiction(a, q, fallback=False)
    case(f"contradiction: {name}", _out.strip() != a.strip(), want_stripped)


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
