"""Why a note loses a query: the ranking arithmetic, term by term.

search_vault returns the winner and nothing else, so every ranking question up
to now has been answered by changing a constant and re-running the suite. That
finds whether a change helped; it never says what was wrong.

This prints the working: the rarity and document frequency of each query term,
what each candidate matched it on, and the multipliers applied afterwards.

    docker exec orb-remote python3 /app/diag_score.py \\
        "how much water for rice" rice.md ref2-cooking-ratios.md

The first argument is the query; any names after it are notes to print even if
they rank below the top five.

It found the bug it was written for on the first run. "how much water for rice"
returned the Wikipedia article on rice rather than the cheatsheet that answers
the question, and the weights were not the reason: "much" was surviving as a
query term with a rarity of 2.09, rice.md contained the word and the cheatsheet
did not, and coverage - which multiplies the entire score - therefore read 1.00
against 0.75. A function word was choosing the answer. That is visible in one
line of this output and in nothing search_vault returns.

Diagnostic only: nothing imports it, and the router does not know it exists.
"""
import math
import sys

sys.path.insert(0, "/app")
import remote_proxy as R  # noqa: E402


def score_of(n, terms, rarity, info, avg_len, operational):
    """search_vault's score for one note, and the parts it is made of.

    Deliberately a transcription of the loop in search_vault rather than a
    call into it, because that loop only ever yields its maximum. The risk is
    that the two drift apart and this quietly reports the arithmetic of a
    version that no longer runs - so it is kept adjacent to the original, and
    the totals here were checked against the score search_vault returns.
    """
    title_w, body_w = set(n["_tw"]), set(n["_bw"])
    base = matched = 0.0
    parts = []
    for w in terms:
        if w in title_w:
            base += 3.0 * rarity[w]
            parts.append(f"{w}:title")
        elif w in body_w:
            base += 1.0 * rarity[w]
            parts.append(f"{w}:body")
        else:
            continue
        matched += rarity[w]

    if not matched:
        return None

    coverage = matched / info
    length = (1 - R.LENGTH_B) + R.LENGTH_B * (len(n["_bw"]) / avg_len)
    generated = 0.7 if n.get("generated") else 1.0
    source = 0.25 if n["file"].startswith("src-") else 1.0
    ref = 1.15 if (operational and n.get("reference")) else 1.0

    total = base * coverage / length * generated * ref
    return total, base, coverage, length, generated, source, ref, parts


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    query, wanted = sys.argv[1], set(sys.argv[2:])

    R.load_vault()
    raw = R.key_terms(query)
    terms = [R._stem(w) for w in raw]
    if not terms:
        raise SystemExit("  no query terms survive key_terms - all stopwords?")

    df = R._build_index()
    total_notes = len(R._vault)
    operational = bool(R._OPERATIONAL.search(query.lower()))
    rarity = {w: math.log(1 + total_notes / max(1, df.get(w, 1))) for w in terms}
    info = sum(rarity.values()) or 1.0
    avg_len = (sum(len(n["_bw"]) for n in R._vault) / total_notes) or 1.0

    print(f"query        {query!r}")
    print(f"terms        {raw} -> {terms}")
    print(f"operational  {operational}    notes {total_notes}    "
          f"avg body {avg_len:.0f} words")
    for w in terms:
        print(f"  {w:14} rarity {rarity[w]:6.3f}   df {df.get(w, 0):5}")
    print()

    rows = []
    for n in R._vault:
        got = score_of(n, terms, rarity, info, avg_len, operational)
        if got:
            rows.append((got, n))
    rows.sort(key=lambda r: -r[0][0])

    print("rank   score    base   cov    len    gen    ref   file")
    for i, ((total, base, cov, length, gen, src, ref, parts), n) in \
            enumerate(rows, 1):
        if i > 5 and n["file"] not in wanted:
            continue
        print(f"{i:4}  {total:7.2f}  {base:6.2f}  {cov:.2f}  {length:5.2f}  "
              f"{gen:.2f}  {ref:.2f}   {n['file']}  [{', '.join(parts)}]")
        if i > 5:
            wanted.discard(n["file"])
    for missing in sorted(wanted):
        print(f"      ------  {missing}: matched no query term at all")


main()
