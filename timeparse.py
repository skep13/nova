"""The time grammar behind reminders and timers, shared by both surfaces.

Extracted from nova_bridge.py when reminders stopped being Telegram-only. The
parser had been the reason they were: everything else a reminder needs — a
store, a sweep, a way to reach him — already worked from anywhere, and only
"in twenty minutes" lived exclusively in the bridge.

Kept as one module rather than copied, because two copies of a time parser
drift and the failure mode is the worst kind available here: a reminder that
silently never fires is indistinguishable from one that was never set, and he
finds out by missing the thing.

parse_when() is imported by nova_bridge.py and by remote_proxy.py, and is
exercised by test_nova.py through the bridge.
"""
import re
import time


# Parsed, not modelled. "in twenty minutes" and "at half seven" are a small
# regular grammar, and the failure modes of getting them wrong are the worst
# kind: a reminder that silently never fires is indistinguishable from one that
# was never set, and the user finds out by missing the thing.
#
# So the clock is arithmetic and the only thing the model would have been asked
# for — what the reminder is ABOUT — is just the rest of the sentence.
_UNITS = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
          "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
          "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
          "d": 86400, "day": 86400, "days": 86400,
          "w": 604800, "week": 604800, "weeks": 604800}

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "forty-five": 45, "fortyfive": 45, "sixty": 60, "half": 0.5,
}

# "in" and "for" both: a reminder is set "in 20 minutes" and a timer is set
# "for 10 minutes", and both are the same arithmetic.
_IN = re.compile(
    r"\b(?:in|for)\s+(\d+|" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) +
    r")\s*(" + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")\b", re.I)

_AT = re.compile(r"\bat\s+(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", re.I)

# Matched separately and removed before the time is parsed, rather than being
# an optional group on either side of it. As part of _AT it had to be written
# twice, the trailing copy never fired because the preceding \s* had already
# eaten its space, and "at 8 tomorrow" became eight tonight with the word
# "tomorrow" left sitting in the reminder text.
_TOMORROW = re.compile(r"\btomorrow\b", re.I)

_REMIND = re.compile(
    r"^\s*(?:can you\s+|please\s+)*(?:remind me|set a reminder|reminder)\b(.*)$", re.I)
_TIMER = re.compile(
    r"^\s*(?:can you\s+|please\s+)*(?:set (?:a|an)\s+|start (?:a|an)\s+)?timer\b(.*)$",
    re.I)
_LIST_REM = re.compile(r"^\s*(?:reminders|timers|list reminders|what.s set)\s*[?.]?\s*$", re.I)
_CANCEL = re.compile(r"^\s*cancel\s+(?:reminder\s+)?(\d+|all)\s*$", re.I)


def parse_when(text, now=None):
    """(epoch, remaining_text) for a time phrase, or (None, text).

    Handles "in 20 minutes" and "at 7pm", with "tomorrow" on either side of the
    time. An "at" time that has already passed today rolls to tomorrow, because
    someone saying "remind me at 7" at nine in the evening does not mean two
    minutes ago and does not mean never.
    """
    now = now or time.time()

    tomorrow = bool(_TOMORROW.search(text))
    if tomorrow:
        text = _TOMORROW.sub(" ", text)

    m = _IN.search(text)
    if m:
        raw, unit = m.group(1).lower(), m.group(2).lower()
        n = float(raw) if raw.isdigit() else _WORD_NUMBERS.get(raw, 0)
        if n <= 0:
            return None, text
        return now + n * _UNITS[unit], (text[:m.start()] + " " + text[m.end():]).strip()

    m = _AT.search(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if hour > 23 or minute > 59:
            return None, text
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        # No am/pm and an hour that has already gone today is read as the
        # evening: "remind me at 7" said at lunchtime means seven tonight, not
        # tomorrow morning.
        #
        # Not when tomorrow was said, though. "tomorrow at 8" means eight in
        # the morning, and shifting it by today's clock turned it into eight at
        # night — the reminder arrives, twelve hours late, which is the failure
        # that looks least like a failure.
        lt = time.localtime(now)
        assume_pm = (not ampm and not tomorrow and hour < 12
                     and (lt.tm_hour, lt.tm_min) > (hour, minute)
                     and hour + 12 > lt.tm_hour)
        if assume_pm:
            hour += 12
        target = list(lt)
        target[3], target[4], target[5] = hour, minute, 0
        when = time.mktime(time.struct_time(tuple(target)))
        if tomorrow or when <= now:
            when += 86400
        return when, (text[:m.start()] + " " + text[m.end():]).strip()

    return None, text


def clean_task(text):
    """The reminder itself, with the connecting words taken off the front."""
    t = re.sub(r"^\s*(?:to|that|about|it.s|its)\b\s*", "", text.strip(), flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.;:")
    return t


