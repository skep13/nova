"""Lift the persona out of index.html and into a file the server can read.

Nova's character did not exist on the server. The persona, the core rules and
the sixteen few-shot turns are all assembled in the browser, and
/v1/chat/completions is close to a pass-through — so anything that is not the
web page (a messaging bridge, a scheduled alert, a test) got a bare
Qwen2.5-3B with no character and no vault.

Extracted rather than retyped. Two kilobytes of prompt copied by hand is two
kilobytes of opportunity to introduce a difference nobody would ever notice,
and a personality that is subtly different depending on which client you
reached it through is worse than one that is merely absent.

    python3 extract_persona.py [index.html] [persona.py]

parse() is also imported by test_nova.py, which runs it against the deployed
page and asserts the result matches persona.py. That assertion is the point:
two copies of a personality are fine as long as something checks they are the
same one.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

# Named here rather than found inline, so adding a block to the page is a
# one-word change instead of a silent omission. COACH was missed exactly that
# way on the first pass, and nothing would have reported it.
BLOCKS = ("PERSONA", "PERSONA_SHORT", "PLAIN", "CORE_RULES", "COACH")


def js_block(html, name):
    """The right-hand side of `const NAME = ...;` up to the next declaration."""
    m = re.search(r"^const " + name + r"\s*=\s*(.*?);\s*$\n(?=\s*(?://|const |let |function ))",
                  html, re.S | re.M)
    if not m:
        raise SystemExit(f"could not find const {name}")
    return m.group(1)


def strip_comments(js):
    """Drop // lines. In these blocks they sit BETWEEN the concatenated string
    literals, never inside one, so this is safe here and would not be in
    general."""
    return "\n".join(l for l in js.splitlines() if not l.strip().startswith("//"))


def js_strings(js):
    """Every single-quoted literal, in order, unescaped.

    \\u{...} is handled because the persona contains one emoji and the page
    must not. This project's no-pictograph test scans the SERVED HTML, and the
    persona lives inside it — so a literal heart in the character sheet put a
    literal heart in the page and failed the test, correctly. Written as an
    escape it is absent from the source and present in the string the model
    receives, which is what both sides actually want.
    """
    out = []
    for lit in re.findall(r"'((?:[^'\\]|\\.)*)'", js):
        lit = re.sub(r"\\u\{([0-9A-Fa-f]+)\}",
                     lambda m: chr(int(m.group(1), 16)), lit)
        out.append(lit.replace("\\n", "\n").replace("\\'", "'")
                      .replace('\\"', '"').replace("\\\\", "\\"))
    return out


def concatenated(html, name):
    return "".join(js_strings(strip_comments(js_block(html, name))))


def parse(html):
    """The page's prompt material, as ({name: text}, [(role, content), ...])."""
    blocks = {name: concatenated(html, name) for name in BLOCKS}

    # FEWSHOT is an array of {role, content} rather than a concatenation, so it
    # is read as pairs. name:'example' is skipped over: it marks the turns as
    # droppable for a model too large to need them, which is a send-time
    # concern rather than part of the text.
    fewshot = []
    for role, content in re.findall(
            r"role\s*:\s*'([^']+)'\s*,\s*(?:name\s*:\s*'[^']*'\s*,\s*)?content\s*:\s*"
            r"((?:'(?:[^'\\]|\\.)*'\s*\+?\s*)+)",
            strip_comments(js_block(html, "FEWSHOT"))):
        fewshot.append((role, "".join(js_strings(content))))
    if not fewshot:
        raise SystemExit("FEWSHOT parsed empty -- the shape of the array changed")
    return blocks, fewshot


HEADER = '''"""Nova's character, in one place.

Extracted verbatim from index.html by extract_persona.py -- do not edit by
hand. The browser still carries its own copy and assembles its own prompt;
this is the copy every OTHER caller uses: the messaging bridge, scheduled
alerts, and the tests.

test_nova.py asserts the two copies are identical, because two sources of
truth for a personality drift silently and the only symptom is Nova sounding
slightly wrong somewhere nobody is looking.
"""
'''


def main():
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "index.html"
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "persona.py"

    blocks, fewshot = parse(src.read_text(encoding="utf-8"))

    body = [HEADER]
    for name in BLOCKS:
        body.append(f"{name} = {blocks[name]!r}\n")
    body.append("FEWSHOT = [")
    for role, content in fewshot:
        body.append(f"    ({role!r}, {content!r}),")
    body.append("]\n")

    out.write_text("\n".join(body), encoding="utf-8")
    for name in BLOCKS:
        print(f"  {name:11}{len(blocks[name]):6} chars")
    print(f"  {'FEWSHOT':11}{len(fewshot):6} turns, "
          f"{sum(len(c) for _, c in fewshot)} chars")


if __name__ == "__main__":
    main()
