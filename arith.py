"""Arithmetic, done by arithmetic.

The one capability in eval_models.py with no gate in front of it. Every other
job a message can ask for — the weather, a reminder, a note, a lookup — is
routed by a regex and executed by code, and the model only ever writes the
sentence around the result. Sums went to the model itself, and the model is the
worst tool in the box for them: Qwen3-4B gets the tank question right slowly,
MiniCPM5-1B reasoned about it until its token budget ran out and returned
NOTHING, and neither can say why it believes its answer.

So this is the gate that was missing. It matters more for a small model than a
large one, which is the point: moving work out of the model is what makes a 1B
viable, and it costs zero model calls instead of the two that tool-calling
would.

Deliberately NOT a general expression evaluator on user text. It parses a small
set of shapes it can be sure about and declines everything else — declining is
free, because the model is still there behind it. A calculator that is right
99% of the time is worse than one that answers 40% of questions and is never
wrong, because the 1% is indistinguishable from the rest.

    >>> solve("what is 240 - 18 + 15")
    ('237', '240 - 18 + 15')
    >>> solve("what did i have for dinner")
    (None, None)
"""
import re

# A plain sum: digits, operators, brackets and nothing else. The characters are
# the whitelist — there is no eval() here and nothing that is not one of these
# ever reaches the arithmetic.
_SAFE = re.compile(r"^[\d\s+\-*/×÷^().,%]+$")

# The lead-ins people actually type. Anchored, so "what is 2 + 2" is a sum and
# "the cable that is 2 metres" is not.
_ASK = re.compile(
    r"^\s*(?:what(?:'s| is)|whats|calculate|compute|work out|how much is|"
    r"how many is|solve|evaluate)\s+(.+?)\s*[?.!]*\s*$", re.I)

# A percentage, which is the one word-shape common enough to be worth parsing.
_PERCENT = re.compile(
    r"^\s*(?:what(?:'s| is)|whats)?\s*([\d.]+)\s*%\s*(?:of|off)\s+([\d.,]+)\s*[?.!]*\s*$",
    re.I)


def _tidy(n):
    """A number a person would write: 237, not 237.0; 0.5, not 0.50000000001."""
    if isinstance(n, int) or n == int(n):
        return str(int(n))
    return f"{round(n, 6):g}"


def _arith(expr):
    """Evaluate a whitelisted arithmetic string, or return None.

    Uses Python's own parser rather than a hand-rolled one, but only after the
    text has been proved to contain nothing but digits and operators — so there
    is no name, no call, no attribute and no import that could be reached even
    if the check were wrong about precedence.
    """
    expr = (expr or "").strip()
    if not expr or not _SAFE.match(expr):
        return None
    # Thousands separators, and the symbols people type instead of * and /.
    expr = expr.replace(",", "").replace("×", "*").replace("÷", "/")
    expr = expr.replace("^", "**")
    if not re.search(r"\d", expr) or not re.search(r"[+\-*/%]", expr):
        return None
    # Exponentiation is the one operation here that can hang rather than fail.
    #
    # The first guard checked for a three-digit exponent literal and let
    # "9**9**9" straight through — which is right-associative, so it is 9 to
    # the power of 387,420,489, and Python sets about computing it. The test
    # suite for this file hung on that line rather than failing, which is the
    # worst way for a bug to present.
    #
    # So: one ** at most, and a small exponent. Anything more exotic goes to
    # the model, which is a fine outcome.
    if expr.count("**") > 1:
        return None
    exponent = re.search(r"\*\*\s*(\d+)", expr)
    if exponent and int(exponent.group(1)) > 32:
        return None
    if len(re.sub(r"\D", "", expr)) > 24:
        return None
    try:
        # compile() with eval mode over a string already proved to hold only
        # digits and operators. No builtins, no globals, nothing to reach.
        value = eval(compile(expr, "<arith>", "eval"), {"__builtins__": {}}, {})
    except Exception:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def solve(text):
    """(answer, what_was_calculated), or (None, None) if this is not a sum.

    The second element is returned so the reply can show its working. A number
    on its own is a claim; a number next to the sum it came from is checkable,
    which is the whole reason this exists rather than trusting the model.
    """
    text = (text or "").strip()
    if not text:
        return None, None

    m = _PERCENT.match(text)
    if m:
        try:
            pct, whole = float(m.group(1)), float(m.group(2).replace(",", ""))
        except ValueError:
            return None, None
        return _tidy(whole * pct / 100), f"{m.group(1)}% of {m.group(2)}"

    m = _ASK.match(text)
    expr = m.group(1) if m else text
    value = _arith(expr)
    if value is None:
        return None, None
    return _tidy(value), expr.strip()
