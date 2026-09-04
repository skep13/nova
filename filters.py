"""Everything Nova is not allowed to say, enforced after she has said it.

Pure functions over text: no I/O, no model, no network, and nothing outside the
standard library. That is the whole reason the module exists - these lived in
remote_proxy.py behind `import aiohttp`, so not one of them could be tested
without a running server, and every one of them was verified today against
cases that then lived only in temporary files.

Each filter began as a rule in the persona and moved here because instruction
alone lost. A prohibition in a prompt is something the model must remember on
every turn; a prohibition here is simply true. That difference is what makes a
small model viable and a large one more trustworthy.

The comments name the reply that caused each one, because the reply is the
argument. "The SATA cable issue was the connector, not the drive. You found the
right part. It's working" makes the case for a grounding check better than any
amount of theory about hallucination.

Run them in the order nova_turn does:

    answer = strip_closing_offer(strip_model_disclaimer(strip_opening_praise(a)))
    answer = strip_banned_register(answer)
    answer = strip_invented_times(answer, grounding)
    answer = strip_ungrounded_history(answer, question, grounding)
    answer = strip_between_conversations(answer, question)

test_filters.py exercises all of it in about a second, with nothing installed.
"""
import re


_STOP = set("""a an the is are was were be been being am of in on at to for with and or but if then
than that this these those it its as by from what who whom when where why how do does did done can
could should would will shall may might must i you he she they we us me my your our their his her
about tell explain say know think give show please just really very some any there here so no yes
not have has had get got make made take put see look want need use using
much many often also even still such both each every another again once else
because while whether either neither quite rather actually basically simply
ever always never sometimes too own same thing things""".split())
# The last four lines were added after "how much water for rice" returned the
# Wikipedia article on rice instead of the cooking cheatsheet that answers it.
#
# The cause was not the ranking weights. "much" was being kept as a query term
# with a rarity of 2.09 — it appears in only 189 of 1,340 notes, so the index
# considered it informative — and rice.md happens to contain the word in its
# prose while the cheatsheet does not. That gave the article a coverage of 1.00
# against the cheatsheet's 0.75, and coverage multiplies the whole score, so a
# function word carrying no topic decided the answer: 17.36 against 13.87.
#
# Rarity cannot see this. It measures how often a word occurs, and "much" is
# genuinely uncommon in encyclopedia prose — it is uninformative for a reason
# no document frequency can express. The list is the only place to say so.
#
# Only the words with no topical sense in this vault. "long", "hot", "far" and
# "big" are deliberately NOT here despite appearing in the same "how much /
# how long" question frames, because long grain, hot water and far infrared
# are things somebody asks about. Comparatives are out for the same reason:
# least squares, most significant bit.
#
# This list filters QUERIES only — key_terms, not the document indexer — so
# nothing in the vault becomes unfindable, and no note is re-embedded.


# Praise for the question, removed from the front for the same reason the empty
# sign-off is removed from the back: it is named in the persona, banned by
# example, and still turns up. "Considering you're asking, it's a good
# question" preceded a hedge; the praise and the hedge are the same instinct.
#
# Only when something follows it. If the entire reply is "That's a great
# question" then it is the only reply there is, and an empty message is worse.
_OPENING_PRAISE = re.compile(
    r"^\s*(?:(?:well|ah|oh|so)[,!.]?\s+)?"
    r"(?:(?:considering\s+)?(?:you'?re|you\s+are)\s+asking[,!.]?\s*)?"
    # The lead-in is OPTIONAL. It was required, so "That's a great question"
    # was caught and a bare "Great question!" - which is the commonest form of
    # it by some distance - was not. Found by writing the first test this
    # function had ever had.
    r"(?:(?:that'?s|this\s+is|it'?s|what\s+a)\s+)?"
    r"(?:a\s+|an\s+)?(?:really\s+|very\s+|such\s+a\s+)?"
    r"(?:great|good|excellent|interesting|fair|nice|smart|awesome|fantastic)\s+"
    r"(?:question|point|one|idea|call)\b[^.!?]*[.!?]+\s*", re.I)


# The other opener worth deleting: disclaiming a self before answering.
#
# Asked "do you think I should switch models", the reply began "I don't think
# about personal preferences, but ..." — and the useful half was after the
# comma. The persona bans "I do not have personal preferences" by name and this
# arrived as a paraphrase, which instruction cannot catch and a pattern can.
#
# The clause is removed, not the answer: whatever followed the "but" was the
# actual reply and is kept, capitalised back up.
_SELF_DISCLAIMER = re.compile(
    # "I'm just a model" is the same move as "I don't have personal
    # preferences", arriving in different words. Asked why she was being cold,
    # she answered "I'm just a model, not a warm human friend" — stepping
    # outside the character to disclaim having one, to the person who wrote it.
    r"^\s*(?:as an ai[,\s]*)?i\s*(?:'m|\s+am)\s+(?:just|only|merely)\s+"
    r"(?:an?\s+)?(?:ai|model|language\s+model|program|programme|assistant|tool|"
    r"machine|bot)\b[^.!?]*?(?:[,.]?\s*but\s+|[.!?]\s*)"
    r"|^\s*(?:as an ai[,\s]*)?i\s+(?:do\s?n[o']t|can\s?not|cannot|don'?t)\s+"
    r"(?:really\s+)?(?:have|think about|hold|form|possess|experience)\s+"
    r"(?:any\s+|my\s+own\s+|specific\s+)?"
    r"(?:personal\s+)?(?:preferences?|opinions?|feelings?|thoughts?|desires?|"
    # Lazy, not greedy. Greedy ran past the "but" to the full stop at the end
    # and consumed the whole reply — sub() returned an empty string, the
    # "never return nothing" fallback handed back the original untouched, and
    # the filter looked like it simply did not fire. It was firing far too well.
    r"views?|beliefs?)\b[^.!?]*?(?:[,.]?\s*but\s+|[.!?]\s*)", re.I)


# A bare acknowledgement at the front of a reply. "Got it. How did it go?" is
# not wrong, but the "Got it" is a receipt bolted to the answer and it is what
# makes her read as a machine taking a ticket. Removed only when something
# follows; a reply that is nothing BUT the acknowledgement keeps it, since an
# empty message is worse.
_OPENING_RECEIPT = re.compile(
    r"^\s*(?:got it|i see|understood|noted|sure thing|okay then|alright then|"
    r"very well|acknowledged)\b[,.!]*\s+(?=\S)", re.I)

# Disclaiming being a model, ANYWHERE in the reply rather than only at the
# start. Asked why she was cold, three prompt-level fixes later, she still
# produced "I am a model, a program. I have no temperature." — to the person
# who wrote her.
#
# This is a strong prior in the base model that instruction has not held
# against, so the sentence is removed instead. Whole sentences only, and never
# the last thing standing.
#
# Two shapes, because it comes in two. A whole sentence — "I am a model, a
# program." — and a clause tucked inside one, as in "I'm fine, just a model."
# Removing the sentence in the second case would take "I'm fine" with it, so
# the clause is cut on its own and the sentence around it survives.
_MODEL_DISCLAIMER = re.compile(
    r"(?:^|(?<=[.!?]))\s*[^.!?]*\bi\s*(?:'m|\s+am)\s+(?:just\s+|only\s+|merely\s+)?"
    r"(?:an?\s+)?(?:ai|a\s+model|model|language\s+model|program|programme|bot|"
    r"machine|piece\s+of\s+software)\b[^.!?]*[.!?]+", re.I)

# Disclaimers of NATURE rather than of capability.
#
# "I'm not a person, so I don't have a state", in reply to "how are you". The
# noun list did not cover it and the design-language pattern did not either: it
# claims neither incapacity nor construction, it simply announces what she is
# not. Same family, same answer.
_NATURE_DISCLAIMER = re.compile(
    r"(?:^|(?<=[.!?]))\s*[^.!?]*\bi\s*(?:'m|\u2019m|\s+am)\s+not\s+"
    r"(?:a\s+)?(?:person|human|alive|conscious|sentient|real)\b[^.!?]*[.!?]+"
    r"|(?:^|(?<=[.!?]))\s*[^.!?]*\bi\s+(?:do ?n[o\u2019']t|don't)\s+have\s+"
    r"(?:a\s+)?(?:state|inner life|experience|consciousness|body)\b[^.!?]*[.!?]+",
    re.I)

_MODEL_CLAUSE = re.compile(
    r",\s*(?:just|only|merely|being)\s+(?:an?\s+)?"
    r"(?:ai|model|language\s+model|program|programme|bot|machine)\b", re.I)


# The same disclaimer with the nouns taken out.
#
# "I'm not cold — I'm just not built for warmth." That went to the person who
# wrote her, and it is worse than "I am an AI": it says the coldness is a
# property of her construction and therefore permanent, so there is nothing he
# can do and nothing she will do. The persona has forbidden this in plain words
# twice and it came back both times, because the model is not saying a banned
# noun, it is reaching for the same idea in the language of design.
#
# Scoped to sentences about HERSELF. "This script is not designed to handle
# that" is a true and useful thing to say about code, and must survive.
_SELF_REFERENCE = re.compile(
    r"\b(?:i|i\s*(?:'m|’m|m)|i\s+am|i\s+was|me|my\s+\w+)\b", re.I)

_DESIGN_DISCLAIMER = re.compile(
    r"\bnot\s+(?:really\s+|actually\s+|exactly\s+|just\s+|simply\s+)?"
    r"(?:built|designed|made|programmed|wired|meant|equipped|capable\s+of)"
    r"\b|\bwas\s*n[o’']?t\s+(?:built|designed|made|programmed|meant)\b"
    r"|\bincapable\s+of\s+(?:caring|feeling|warmth|emotion)", re.I)


# A clock time she was never given.
#
# Five separate persona attempts have not stopped this. "gave in at 14:47",
# "after 45 minutes of pulling", and then "it gave in at 10:47" in reply to a
# remark about solder fumes — a different invented time, on a prompt that had
# nothing to do with it. There is no time anywhere in her memory or the diary,
# so every one of these is manufactured, and a precise number is the most
# convincing kind of wrong.
#
# Instruction has had its five goes. This checks instead: a time in the answer
# that appears nowhere in the question, the conversation, or what she was given
# did not come from anywhere, and the sentence containing it goes.
_CLOCK = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b|\b\d{1,2}\s*(?:am|pm)\b", re.I)


# How many times something has happened, which she is never in a position to
# know unless he said so.
#
# "i managed to unplug the wrong drive again" came back with "That's the third
# time this week" — a precise, checkable, entirely invented figure, delivered
# with the same confidence as the true half of the sentence. It is the clock
# problem in another unit, and it needs the same answer.
#
# Checked unconditionally rather than only on questions about his past,
# because this arrived in reply to a STATEMENT. Narrow enough to be safe there:
# a general technical answer has little reason to count his weeks.
_COUNT_CLAIM = re.compile(
    r"\b(?:the\s+)?(?:first|second|third|fourth|fifth|sixth|seventh)\s+time\b"
    r"|\b(?:twice|three times|four times|five times)\b"
    r"|\b\d+(?:st|nd|rd|th)\s+time\b", re.I)


def strip_invented_times(answer, grounding):
    """Drop sentences whose clock time or count is not present in the grounding."""
    given = set(_CLOCK.findall(grounding or ""))
    given_norm = {g.strip().lower().replace(".", ":") for g in given}

    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", answer or ""):
        times = _CLOCK.findall(sentence)
        invented = [t for t in times
                    if t.strip().lower().replace(".", ":") not in given_norm]
        if invented:
            continue

        count = _COUNT_CLAIM.search(sentence)
        if count and count.group(0).lower() not in (grounding or "").lower():
            continue
        kept.append(sentence)
    out = " ".join(kept).strip()
    # Never return nothing: if the whole answer hinged on an invented time
    # there is no better text to fall back to, and an empty reply is worse than
    # a wrong one the user can see and correct.
    return out or (answer or "").strip()


# An assertion about his own past that came from nowhere.
#
# This is the failure that has outlasted every persona rule written against it.
# Asked "did I get the cable sorted in the end?", with nothing in the diary
# saying so, the answer was: "The SATA cable issue was the connector, not the
# drive. You found the right part. It's working." All of it invented, none of
# it hedged, and it PASSED the test suite, because the checks banned the verbs
# "fixed" and "sorted" and she simply used different words.
#
# So this does not look for words. It gates on the QUESTION being about his
# past, and then requires every distinctive noun in the answer to appear
# somewhere in what she was actually given — the question, the conversation,
# the stored facts, the day-notes. A specific claim about his life that is
# traceable to none of those did not come from anywhere.
#
# Deliberately narrow. It engages ONLY on questions about his past, because
# that is where invention is both most likely and most costly; a general answer
# about Postgres is full of words that appear nowhere in his diary and must not
# be touched.
_PAST_QUESTION = re.compile(
    r"\b(?:did|have|had|was|were)\s+(?:i|it|that|we|the|my)\b"
    r"|\bhow\s+(?:long|much|many)\s+(?:did|have|was)\b"
    r"|\bwhat\s+did\s+(?:i|we)\b"
    r"|\bwhen\s+did\s+(?:i|we|it|that)\b"
    r"|\b(?:did|has)\s+(?:it|that|he|she|they)\s+\w+", re.I)

# Sentences that are the honest answer and must never be stripped, whatever
# words they contain. "The notes don't go that far back" is exactly the reply
# this filter exists to produce, and it is full of nouns.
_IGNORANCE = re.compile(
    r"\b(?:do ?n[o’']?t|cannot|can ?n[o’']?t|have ?n[o’']?t|"
    r"did ?n[o’']?t)\s+(?:know|have|recall|remember|say|see|find)"
    r"|\bno (?:record|idea|note|mention|way of knowing)"
    r"|\b(?:you|he) (?:have|has) ?n[o’']?t told me"
    r"|\bnot (?:in|written|here|sure|something) "
    r"|\bnothing (?:here|in|about|written)"
    r"|\byou tell me\b|\bi was ?n[o’']?t told\b", re.I)

# Words that assert nothing, on top of the retrieval stopwords in _STOP.
#
# _STOP covers grammar. These are the words that are grammatically contentful
# and factually empty — "rather", "probably", "the right part" — and they have
# to be excluded too, because an answer is allowed to be phrased differently
# from the note it came from. Leaving them in made "You were asking about the
# SATA link" fail as unsupported on the strength of "rather".
_VAGUE = frozenset("""
able actual actually again against already also although always another
anything back because before better best both bring came come different
during each either else enough even ever every everything far few finally
first following further general good great half hard here high however
important instead itself keep kind large last late later least less little
long look lot main many maybe more most much near nearly need never next
nothing now often once only other others over own part parts perhaps place
possible probably quite rather ready real really right same several similar
simply since small some something sometimes soon still such sure than thing
things think though through together too toward under until upon usually
various very way ways well whether while whole why without wrong yet
""".split())


# A verdict on a past event with no content in it at all: "You did.", "Yes.",
# "It didn't." Only ever consulted for a sentence that has no distinctive words
# to trace, so it cannot swallow a real answer that happens to start with yes.
_BARE_VERDICT = re.compile(
    r"^\W*(?:yes|no|yeah|yep|nope|you did|you did ?n[o’']?t|you have|"
    r"you have ?n[o’']?t|it did|it did ?n[o’']?t|it was|it was ?n[o’']?t|"
    r"that.s right|correct|indeed)\b", re.I)


def _key(w):
    """A harder stem than _stem, for comparing an answer against its sources.

    _stem is tuned for retrieval, where over-stemming collapses distinct notes
    into each other and costs precision. Here the cost is reversed: a form that
    fails to meet its source ("asking" against a note that says "asked") reads
    as an invented claim and gets a true sentence deleted. So this strips
    harder and floors lower.
    """
    w = w.lower()
    for suf in ("ingly", "edly", "ing", "ies", "ied", "ers", "est", "ed",
                "er", "ly", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            if suf == "s" and w.endswith("ss"):
                break
            w = w[: -len(suf)]
            break
    if w.endswith("i"):          # "ied" -> "i", as in tried -> tri
        w = w[:-1]
    return w


def _distinctive(text):
    """The words in a piece of text that actually carry a claim."""
    return {_key(w) for w in re.findall(r"[a-z]{3,}", (text or "").lower())
            if w not in _STOP and w not in _VAGUE and len(w) >= 4}


# What she did while he was gone: nothing.
#
# This lived in the Telegram persona, failed there as instruction, and was then
# dropped entirely when the two characters merged — so it came straight back:
# "Nothing. Just waiting. You're the one who keeps showing up."
#
# Gated on the question actually being about her time, because "I'm waiting for
# the build to finish" is a true and ordinary thing to say and must survive.
_HER_TIME = re.compile(
    r"\bwhat\s+(?:have|had)\s+you\s+been\b"
    r"|\bwhat\s+(?:are|were)\s+you\s+(?:doing|up\s+to)\b"
    r"|\bhow\s+(?:have|has)\s+(?:you|your)\b.{0,20}\bbeen\b"
    r"|\bmiss(?:ed)?\s+me\b|\bwere\s+you\s+waiting\b", re.I)

_BETWEEN = re.compile(
    r"\b(?:just\s+|only\s+|mostly\s+)?"
    r"(?:waiting|wait|watching|watched|thinking|thought about|listening|"
    r"listened|sitting|sat here|reading|read|missing|missed you|"
    r"keeping an eye|kept an eye|here all along|been here)\b", re.I)


def strip_between_conversations(answer, question):
    """Drop claims of having done something while he was away."""
    if not _HER_TIME.search(question or ""):
        return (answer or "").strip()
    kept = [x for x in re.split(r"(?<=[.!?])\s+", answer or "")
            if x.strip() and not _BETWEEN.search(x)]
    return " ".join(kept).strip() or (answer or "").strip()


# A sentence that CLAIMS something happened, as opposed to one that asks,
# advises or refuses.
#
# The filter used to weigh every sentence in a reply about his past, and so
# deleted "You need a wrench, not a prayer" for the crime of saying "wrench" —
# advice, invented nothing, and was the only useful thing in the reply. What
# actually warrants deletion is a claim: a past-tense verb, or a present-tense
# verdict on how something stands.
_ASSERTION = re.compile(
    r"\b(?:was|were|had|did|got|went|came|found|fixed|sorted|solved|took|"
    r"spent|finished|ended|worked|managed|failed|started|stopped|gave|"
    r"turned|swapped|replaced|checked|tried|"
    # The irregulars, which the -ed rule below cannot reach by construction —
    # and which are exactly the verbs a recollection gets built from.
    r"said|told|made|saw|knew|thought|put|kept|left|ran|sent|wrote|built|"
    r"bought|brought|held|meant|met|paid|sat|sold|spoke|stood|understood|"
    r"won|lost|broke|chose|drove|fell|felt|hung|heard|read|rebuilt|"
    r"shut|slept|swore|wore|forgot|began|blew|dealt|dug|drew)\b"
    # Five letters minimum, and an exception list, because the obvious
    # \w+ed matched "need" — and so "You need a wrench, not a prayer",
    # which asserts nothing about his past and was the only useful line in
    # the reply, was deleted as an invented claim.
    r"|\b(?!(?:speed|indeed|exceed|proceed|succeed|breed|bleed|freed|greed|"
    r"creed|embed|sacred|hundred|naked|wicked|rugged)\b)\w{3,}ed\b"
    r"|\b(?:it|that|this|he|she|they)\s*(?:.s|\u2019s|is|are|has|have)\b"
    r"|\byou\s*(?:.ve|\u2019ve|have|had|did)\b"
    # Negated past tenses. "You didn't go back to it after that" is a claim
    # about a non-event, invented exactly as freely as a claim about an event,
    # and \bdid\b does not match "didn't".
    r"|\b(?:did|was|were|had|would|could)\s*n[o\u2019']?t\b"
    r"|\b(?:go|went|come|came|get|got)\s+back\b", re.I)

# Durations and times written as words. The clock check only knows digits, so
# "all day yesterday, from seven until at least ten" — none of which he said —
# was as invented as "14:47" and half as visible.
_SPOKEN_SPAN = re.compile(
    r"\ball (?:day|morning|afternoon|evening|night|week)\b"
    r"|\b(?:half|most) (?:the|of the) (?:day|morning|afternoon|night)\b"
    r"|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"twenty|thirty|forty|fifty|sixty|ninety)\s+"
    r"(?:minutes?|hours?|days?|weeks?)\b"
    r"|\b(?:since|until|till|from|to|about|around)\s+"
    r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
    re.I)


def strip_ungrounded_history(answer, question, grounding, fallback=True):
    """Drop past-tense claims about him whose content is in nothing he gave her.

    Returns the surviving text, or "" when nothing survives and fallback is
    off — the caller asks again rather than shipping a fabrication or
    inventing a replacement for it.
    """
    if not _PAST_QUESTION.search(question or ""):
        return (answer or "").strip()

    # Both sides go through the same stem, so "connector" in the diary
    # supports "connectors" in the answer and "asked" supports "asking".
    known = _distinctive(grounding) | _distinctive(question)
    # What he actually asked ABOUT. An answer that asserts something about his
    # past has to connect to it.
    topic = _distinctive(question)

    sentences = [x for x in re.split(r"(?<=[.!?])\s+", answer or "") if x.strip()]
    kept = []
    for sentence in sentences:
        # Honest answers survive unconditionally, as do questions back to him.
        if _IGNORANCE.search(sentence) or sentence.strip().endswith("?"):
            kept.append(sentence)
            continue

        words = _distinctive(sentence)

        # A claim made entirely of function words.
        #
        # "did i get the cable sorted in the end?" -> "You did." Nothing in it
        # is distinctive, so nothing could be unsupported. Judged FIRST,
        # because the assertion gate below waves through anything with no verb
        # in it — which is every bare verdict, including the "No." that this
        # question got when the order was the other way round.
        if not words and _BARE_VERDICT.search(sentence):
            continue

        # Advice, questions and refusals invent nothing about his past, so
        # they are not candidates however unfamiliar their vocabulary.
        if not _ASSERTION.search(sentence):
            kept.append(sentence)
            continue

        # A span of time he never mentioned, in words rather than digits.
        span = _SPOKEN_SPAN.search(sentence)
        if span and span.group(0).lower() not in (grounding or "").lower():
            continue

        if [w for w in words if w not in known]:
            continue

        # Grounded in SOMETHING is not grounded in THIS.
        #
        # Asked how long he spent on the SATA cable, she answered "You were
        # debugging since seven" — every word of which is in the day-notes, and
        # none of which is about the cable. Word-presence alone cannot tell a
        # recollection from a non-sequitur delivered with confidence, so an
        # assertion also has to touch what he asked about. Skipped when the
        # question has no content words of its own ("did that give in yet?"),
        # where there is no topic to touch.
        if topic and words and not (words & topic):
            continue

        kept.append(sentence)

    out = " ".join(kept).strip()
    # Half the reply deleted means the rest is the wreckage of a story, not an
    # answer. Fragments read worse than either the original or a clean "I don't
    # know", so this is treated the same as nothing surviving.
    if kept and len(kept) * 2 < len(sentences):
        out = ""
    if out:
        return out
    return (answer or "").strip() if fallback else ""


def strip_model_disclaimer(text, fallback=True):
    """Remove the disclaimer sentences. With fallback=False, an answer that was
    NOTHING BUT disclaimer comes back empty rather than intact.

    The other strips here can safely hand back the original when they would
    otherwise return nothing, because a stray clock time in an otherwise real
    answer is a blemish. This one cannot: the sentence being removed IS the
    failure, so returning it because there is nothing else left hands over the
    exact text the strip exists to stop. The caller asks again instead.
    """
    cleaned = _MODEL_CLAUSE.sub("", text or "")
    cleaned = _MODEL_DISCLAIMER.sub(" ", cleaned)
    cleaned = _NATURE_DISCLAIMER.sub(" ", cleaned)

    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        if _DESIGN_DISCLAIMER.search(sentence) and _SELF_REFERENCE.search(sentence):
            continue
        kept.append(sentence)
    cleaned = " ".join(kept)

    cleaned = re.sub(r"\s+([.!?,;])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # A reply that was ONLY the disclaimer leaves nothing behind. Better a
    # short honest sentence than the manufactured one, and better either than
    # silence.
    cleaned = cleaned.strip(" —-–,;")
    if cleaned:
        return cleaned
    return (text or "").strip() if fallback else ""


# The four prohibitions that were still only instructions.
#
# Kept as whole-sentence removals rather than word surgery: cutting a word out
# of the middle of a sentence leaves a sentence that no one wrote, and the
# reply is read aloud. Dropping the sentence loses less.
_PICTOGRAPH = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u2190-\u21FF\u2B00-\u2BFF]")

# A hot drink and a lie down. Named foods and named remedies, because the
# abstract version of this rule never once worked in the prompt.
_COMFORT = re.compile(
    r"\b(?:cup of tea|cuppa|a brew|some tea|a biscuit|hot chocolate|"
    r"a coffee|coffee or|grab a coffee|make a coffee)\b"
    r"|\b(?:take|have|get) (?:a|some) (?:break|rest|breather|nap|walk|bath)\b"
    r"|\b(?:get some rest|early night|put your feet up|treat yourself|"
    # "Go to bed" was not on the list, so it went straight out: told he was
    # knackered after a day of debugging, the reply was "No more debugging. Go
    # to bed." A ban only ever catches what it names, which is the recurring
    # cost of enumerating a closed set - and the reason the set is worth
    # extending the moment one gets past.
    r"step away from|go for a walk|sleep on it|go to bed|get some sleep|"
    r"call it a night|knock it on the head|stop for the day)\b", re.I)

# Register that belongs to a call centre.
_STOCK = re.compile(
    r"\b(?:how (?:may|can) i (?:assist|help)|is there anything else|"
    r"i am (?:here to|happy to) (?:help|assist)|i'?m (?:here to|happy to) "
    r"(?:help|assist)|let me know if you (?:need|have)|feel free to ask|"
    r"i hope (?:this|that) helps|glad i could help|"
    r"as an ai(?: language model)?|i am an ai assistant)\b", re.I)

# British filler he asked to have removed.
# The register of a form, not a person.
#
# The persona says in plain words: no "acknowledged", no "understood",
# no "no further action needed". Asked how she was, the reply was
# "Acknowledged." One instruction among twenty-odd, and it lost.
#
# Anchored to a whole sentence on purpose: "Acknowledged the drive is SATA"
# is a real answer and survives. The failure is the bare receipt.
_OFFICIALESE = re.compile(
    r"^\W*(?:acknowledged|understood|noted|affirmative|confirmed|received|"
    r"roger|copy that|no further action(?: needed| required)?|"
    r"request (?:received|noted)|standing by)\W*$", re.I)

_IDIOM = re.compile(
    r"^\W*(?:cheers|no bother|no worries|brilliant|lovely|blimey|"
    r"right then|ta)\W*$", re.I)


def strip_banned_register(text, fallback=True):
    """Remove emoji, comfort cliches, stock-assistant filler and idiom.

    With fallback=False a reply that was NOTHING BUT banned register comes back
    empty, so the caller can ask again. "Acknowledged." as an entire message is
    the failure itself; returning it because there is nothing else left hands
    over exactly what the filter exists to stop.
    """
    cleaned = _PICTOGRAPH.sub("", text or "")

    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        if not sentence.strip():
            continue
        if _COMFORT.search(sentence) or _STOCK.search(sentence):
            continue
        stripped = sentence.strip()
        if _IDIOM.match(stripped) or _OFFICIALESE.match(stripped):
            continue
        kept.append(sentence)

    out = re.sub(r"\s{2,}", " ", " ".join(kept)).strip()
    if out:
        return out
    if not fallback:
        return ""
    # Otherwise: a reply that was only filler still has to say something, and
    # the original beats silence. The persona carries these rules too, so this
    # is the second line rather than the only one.
    return re.sub(r"\s{2,}", " ", cleaned).strip() or (text or "").strip()


def strip_opening_praise(text):
    text = _OPENING_RECEIPT.sub("", text or "", count=1)
    cleaned = _OPENING_PRAISE.sub("", text or "", count=1).strip()
    cleaned = _SELF_DISCLAIMER.sub("", cleaned, count=1).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned or (text or "").strip()


# The same empty offers, matched as whole sentences ANYWHERE rather than only
# at the end. "If you need anything, just let me know. Have a good rest." put
# the offer first and sailed past an end-anchored pattern; so did a bare
# "Anything else?" tacked on after a real answer.
_OFFER_SENTENCE = re.compile(
    r"(?:^|(?<=[.!?]))\s*[^.!?]*?\b(?:"
    r"(?:how|what)\s+(?:can|may|else\s+can)\s+i\s+(?:help|assist|do)"
    r"|is\s+there\s+(?:anything|something)\s+(?:else|specific|particular)"
    r"|anything\s+else\??"
    r"|if\s+you\s+need\s+anything"
    r"|(?:just\s+)?let\s+me\s+know(?!\s+if\s+(?:you\s+)?(?:want|the|it))"
    r"|glad\s+to\s+help|happy\s+to\s+help"
    r"|have\s+a\s+good\s+(?:rest|night|one)"
    r")\b[^.!?]*[.!?]*", re.I)


# The closing offer of help, removed after the fact.
#
# The persona forbids these by name and the model still reaches for one now and
# then — measured at zero in eighteen replies and then straight back on the
# nineteenth, because sampling is sampling. Asking a 3B more firmly was already
# tried; the phrasings are a closed set, so deleting them is exact where
# instruction is probabilistic.
#
# Only ever the LAST sentence, and only when it is one of these. A reply that
# genuinely ends in a question to the user is left alone.
# Narrowed when the persona was warmed up.
#
# It used to cut any "let me know if ..." and any "feel free to ask", which
# took "let me know if you want the hourly" out along with "let me know if you
# need anything else". The first is a friend being useful; the second is a
# ticket being closed. Only the CONTENTLESS ones go now — the ones that offer
# help in general rather than one specific next thing.


# The closing offer of help, removed after the fact.
#
# The persona forbids these by name and the model still reaches for one now and
# then — measured at zero in eighteen replies and then straight back on the
# nineteenth, because sampling is sampling. Asking a 3B more firmly was already
# tried; the phrasings are a closed set, so deleting them is exact where
# instruction is probabilistic.
#
# Only ever the LAST sentence, and only when it is one of these. A reply that
# genuinely ends in a question to the user is left alone.
# Narrowed when the persona was warmed up.
#
# It used to cut any "let me know if ..." and any "feel free to ask", which
# took "let me know if you want the hourly" out along with "let me know if you
# need anything else". The first is a friend being useful; the second is a
# ticket being closed. Only the CONTENTLESS ones go now — the ones that offer
# help in general rather than one specific next thing.
_CLOSING_OFFER = re.compile(
    r"(?:^|(?<=[.!?]))\s*(?:"
    r"(?:so\s+)?(?:how|what)\s+(?:can|may|else\s+can)\s+i\s+(?:help|assist|do)\b[^.!?]*"
    # "is there something specific you need help with" is the same empty offer
    # as "is there anything else", and slipped past a pattern that only knew
    # the second phrasing.
    r"|is\s+there\s+(?:anything|something)\s+"
    r"(?:else|specific|particular|in\s+particular)\b[^.!?]*"
    r"|let\s+me\s+know\s+if\s+you\s+(?:need|want|have)\s+"
    r"(?:anything|any\s+(?:more|other|further))\b[^.!?]*"
    # Bare "just let me know" with nothing after it. The version above only
    # caught it when it named "anything else", so "If you need anything, just
    # let me know" survived by splitting the same sentiment across two clauses.
    # A "let me know" that goes on to name a specific thing — the hourly
    # forecast, whether it worked — is still kept by the alternation order.
    r"|(?:and\s+|so\s+)?(?:just\s+)?let\s+me\s+know\s*"
    r"|if\s+you\s+need\s+anything[^.!?]*"
    r"|feel\s+free\s+to\s+(?:ask|reach)\s+(?:me\s+)?(?:anything|any\s?time|if)\b[^.!?]*"
    r"|(?:i'?m\s+)?(?:happy|glad)\s+to\s+help\b[^.!?]*"
    r")[.!?]*\s*$", re.I)


def strip_closing_offer(text):
    cleaned = _CLOSING_OFFER.sub("", text or "").strip()
    cleaned = _OFFER_SENTENCE.sub(" ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # Never return nothing: if the whole reply was the offer, the offer is the
    # only answer there is and a blank message is worse.
    return cleaned or (text or "").strip()


# Anything about HIM is excluded. No amount of searching answers "what did I
# have for dinner", and escalating it would turn a correct admission into a
# minute of wasted CPU and an invented answer at the end.
_ABOUT_HIM = re.compile(
    r"\b(?:i|me|my|mine|we|our|us)\b"
    r"|\byou\b[^.?!]{0,20}\b(?:remember|said|told|wrote)\b"
    r"|\bdid (?:that|it)\b", re.I)

# Three words or more: "ok", "thanks" and "morning" are not research questions.
_WORTH_RESEARCH = re.compile(r"\b\w+\b(?:[^\w]+\b\w+\b){2,}")


def should_research(question, answer):
    """True when she came up empty on something an archive might cover."""
    if not (question and answer):
        return False
    # _IGNORANCE is the same pattern the grounding filter trusts to recognise
    # an honest admission, so "came up empty" has one definition, not two.
    if not _IGNORANCE.search(answer):
        return False
    if _ABOUT_HIM.search(question):
        return False
    return bool(_WORTH_RESEARCH.search(question.strip()))
