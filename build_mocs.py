"""Build the hub layer that gives the graph a shape.

Obsidian's graph is a force simulation over links — there is no manual layout,
so the only way to organise it is to change the link topology. 309 notes linked
peer-to-peer settle into one undifferentiated mass. Adding hubs gives the
simulation something to pull against: index -> 5 domains -> 21 topics -> notes.

Nothing existing is modified. A link FROM a hub note creates the same graph edge
as a link from anywhere else, so the whole structure is additive — the 309 notes
are left byte-for-byte alone and only new files appear.

Classification is by keyword rules on the title rather than a hand-written list
of 309 names. Rules survive new notes arriving through /ingest; a hard-coded
list would silently stop covering the vault the first time one did.

Replaces mkindex.py, which generated a flat index and had since become unsafe
to run: it deleted threat-model*.md as a build artefact (that is now a real
note) and emitted [[Title]] links, the exact form that left 1308 of 2073 links
unresolved. This writes index.md too, so the two cannot both own it.

Run fix_links.py after this if any notes were generated in between.
"""
import datetime
import pathlib
import re
import sys

VAULT = pathlib.Path("/opt/orb/mem")
NOW = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

# Ordered: the first rule whose keyword appears in the title wins, so the more
# specific topic must come first. "Heap overflow" has to reach the attack rule
# before "heap" sends it to data structures.
RULES = {
    "security": [
        ("side-channels", "Attacks that read secrets from timing, power or speculative execution rather than from the data itself.",
         ["side-channel", "timing attack", "spectre", "meltdown"]),
        ("cryptography", "Ciphers, hashes, signatures and the key machinery that makes them usable.",
         ["cipher", "crypt", "hash", "hmac", "signature", "key exchange",
          "key derivation", "certificate", "x.509", "public key", "public-key",
          "transport layer", "pretty good privacy", "md5", "sha-", "salt",
          "rainbow table", "steganography", "initialization vector",
          "message authentication", "let's encrypt", "bcrypt", "rsa", "elliptic"]),
        ("identity-and-access", "Proving who someone is, then deciding what they may touch.",
         ["authentication", "access-control", "access control", "role-based",
          "least privilege", "multi-factor", "single sign-on", "oauth",
          "json web token", "kerberos"]),
        ("malware-and-forensics", "Hostile code, and the tooling used to take it apart afterwards.",
         ["malware", "virus", "worm", "trojan", "ransomware", "rootkit",
          "spyware", "keystroke", "forensic", "chain of custody",
          "reverse engineering", "disassembler", "debugger",
          "program analysis", "honeypot", "botnet"]),
        ("attacks-and-offensive", "How systems are actually broken into, and the disciplines built around doing it deliberately.",
         ["spoofing", "brute-force", "dictionary attack", "password cracking",
          "overflow", "shellcode", "return-oriented", "injection",
          "cross-site", "request forgery", "traversal", "exploit",
          "privilege escalation", "race condition", "time-of-check", "replay",
          "man-in-the-middle", "denial-of-service", "zero-day",
          "social engineering", "phishing", "penetration test", "red team",
          "fuzzing", "nmap", "port scanner", "attack surface"]),
        ("defensive-security", "Controls and isolation — the things standing between an attacker and the asset.",
         ["firewall", "intrusion detection", "security information",
          "defense in depth", "incident", "air gap", "sandbox",
          "containerization", "virtual machine", "proxy server",
          "virtual private network", "onion routing", "tor",
          "address space layout", "executable-space"]),
        ("standards-and-governance", "The frameworks, catalogues and scoring systems the industry organises itself around.",
         ["iso/iec", "national institute", "common vulnerabilit", "owasp",
          "information security", "computer security", "data breach"]),
    ],
    "ai": [
        ("language-models", "Transformers, LLMs and the language tasks they absorbed.",
         ["language model", "natural language", "word embedding",
          "machine translation", "named-entity", "sentiment", "prompt",
          "retrieval-augmented", "fine-tuning", "foundation model",
          "hallucination", "perplexity", "speech recognition",
          "optical character", "turing test", "attention", "transformer",
          "mixture of experts", "knowledge distillation"]),
        ("deep-learning", "Network architectures and the mechanics of training them.",
         ["neural network", "deep learning", "perceptron", "activation",
          "softmax", "convolutional", "recurrent", "long short-term",
          "autoencoder", "adversarial network", "diffusion model", "dropout",
          "batch normalization", "vanishing gradient", "neural architecture",
          "backpropagation"]),
        ("classical-ml", "The algorithms that did the work before deep learning, and still win on small data.",
         ["regression", "decision tree", "random forest", "gradient boosting",
          "support vector", "nearest neighbors", "naive bayes", "k-means",
          "principal component", "gaussian process", "hidden markov",
          "anomaly detection", "recommender", "genetic algorithm",
          "simulated annealing"]),
        ("search-and-decision", "Acting under uncertainty: planning, search and reinforcement.",
         ["a* search", "monte carlo", "markov decision", "q-learning",
          "expert system", "symbolic artificial"]),
        ("evaluation-and-metrics", "How you find out whether a model is any good, and how it fails.",
         ["confusion matrix", "precision and recall", "receiver operating",
          "cross-entropy", "bayes' theorem", "loss function",
          "cross-validation", "overfitting", "bias", "regularization",
          "curse of dimensionality", "hyperparameter"]),
        ("ai-safety", "Alignment, interpretability and the failure modes that matter at scale.",
         ["alignment", "ai safety", "explainable"]),
    ],
    "cs": [
        ("networking", "How packets get from one machine to another, and the protocols stacked on top.",
         ["network", "protocol", "osi", "ipv6", "internet",
          "transmission control", "user datagram", "hypertext", "https",
          "domain name", "border gateway", "subnetwork", "secure shell",
          "websocket", "address translation"]),
        ("data-structures", "The containers everything else is built out of.",
         ["array", "linked list", "hash table", "heap", "trie",
          "binary search tree", "data structure", "graph"]),
        ("algorithms", "Sorting, searching, traversal, and the notation for arguing about cost.",
         ["big o", "sorting", "quicksort", "merge sort", "breadth-first",
          "depth-first", "dijkstra", "dynamic programming"]),
        ("systems-and-os", "What the operating system is actually doing underneath a running program.",
         ["operating system", "linux kernel", "process", "thread",
          "concurrency", "mutual exclusion", "semaphore", "scheduling",
          "interrupt", "system call", "virtual memory", "file system",
          "inode", "garbage collection", "finite-state", "compiler",
          "interpreter", "floating-point", "endianness"]),
        ("data-and-tooling", "Storage, encoding and the tools around shipping software.",
         ["database", "sql", "acid", "git", "version control", "docker",
          "kubernetes", "continuous integration", "regular expression",
          "unicode", "utf-8", "base64"]),
    ],
    "field": [
        ("environmental-injury", "What cold, heat, altitude and terrain do to a body.",
         ["hypothermia", "hyperthermia", "heat illness", "frostbite",
          "wind chill", "altitude", "hypoxia", "dehydration", "avalanche"]),
        ("navigation-and-rescue", "Fixing a position, reading ground, and getting help to it.",
         ["navigation", "map reading", "compass", "ordnance survey",
          "distress signal", "mountain rescue", "survival"]),
        ("emergency-care", "Immediate treatment for the injuries a casualty actually presents with.",
         ["first aid", "cardiopulmonary", "bleeding", "fracture", "burn",
          "choking", "concussion", "shock", "sprain", "snakebite",
          "drowning", "tick-borne"]),
    ],
}

FALLBACK = {
    "security": ("security-foundations", "The vocabulary the rest of the security notes assume."),
    "ai": ("ml-foundations", "The ideas every other AI note is built on top of."),
    "cs": ("computing-foundations", "General computing ground that did not fit a narrower topic."),
    "field": ("field-general", "Field craft that spans the other groupings."),
}

DOMAINS = [
    ("security", "Security", "Offensive and defensive security, cryptography and the standards around them."),
    ("ai", "AI and Machine Learning", "From linear regression to transformers, plus how models are evaluated and where they go wrong."),
    ("cs", "Computer Science", "Systems, networks, data structures and the tooling underneath everything else."),
    ("field", "Field and Rescue", "Casualty care, environmental injury and navigation — the notes Orb exists to reach offline."),
    ("orb", "Orb", "The assistant itself: how it is built, what constrains it, and how to fix it."),
]

THREAT_MODEL = """---
created: {now}
title: Threat model
tags: [reference, security]
---

# Threat model

A threat model is a structured statement of who you are defending against,
what you are defending, and what you are willing to lose. It is written down
before controls are chosen, because a control only makes sense relative to an
adversary — [[end-to-end-encryption|end-to-end encryption]] is decisive against
a network eavesdropper and irrelevant against someone with
[[keystroke-logging|a keylogger]] on the endpoint.

The usual questions are: what assets matter, who wants them, what capabilities
those adversaries have, and what happens if they succeed. An adversary with
physical access, one with a foothold on the same network, and one with only a
public interface are three different problems, and a system can be sound
against one while wide open to another.

Threat modelling is what makes [[defense-in-depth|defence in depth]] something
other than a slogan: layers are chosen because a specific adversary is expected
to defeat a specific layer. It is also what stops
[[principle-of-least-privilege|least privilege]] and
[[attack-surface|attack surface]] reduction from being applied uniformly and
expensively everywhere instead of where the risk actually is.

Written for Orb's vault — this note exists because other notes referred to it.
"""


def read_meta(p):
    raw = p.read_text(encoding="utf-8", errors="replace")
    head = raw[:400]
    t = re.search(r"^title:\s*(.+)$", head, re.M)
    g = re.search(r"^tags:\s*\[(.*)\]", head, re.M)
    tags = [x.strip() for x in g.group(1).split(",")] if g else []
    return (t.group(1).strip() if t else p.stem), tags


def classify(title, domain):
    low = title.lower()
    for topic, _desc, keys in RULES.get(domain, []):
        if any(k in low for k in keys):
            return topic
    return FALLBACK[domain][0]


def desc_for(domain, topic):
    for t, d, _ in RULES.get(domain, []):
        if t == topic:
            return d
    return FALLBACK[domain][1]


def frontmatter(title, tags):
    return f"---\ncreated: {NOW}\ntitle: {title}\ntags: [{', '.join(tags)}]\n---\n\n"


def main():
    tm = VAULT / "threat-model.md"
    if not tm.exists():
        tm.write_text(THREAT_MODEL.format(now=NOW), encoding="utf-8")

    buckets = {}
    orb = []
    for p in sorted(VAULT.glob("*.md")):
        if p.stem.startswith("moc-") or p.stem == "index":
            continue
        title, tags = read_meta(p)
        if "moc" in tags:
            continue
        domain = next((d for d in ("security", "ai", "cs", "field") if d in tags), None)
        if "orb" in tags:
            orb.append((title, p.stem))
            continue
        if not domain:
            continue
        buckets.setdefault(domain, {}).setdefault(classify(title, domain), []).append((title, p.stem))

    made = 0
    for domain, dom_title, dom_desc in DOMAINS:
        if domain == "orb":
            lines = [f"- [[{s}|{t}]]" for t, s in sorted(orb)]
            body = (frontmatter(dom_title, ["moc", "orb"])
                    + f"# {dom_title}\n\n{dom_desc}\n\n" + "\n".join(lines)
                    + "\n\nBack to [[index|Index]].\n")
            (VAULT / "moc-orb.md").write_text(body, encoding="utf-8")
            made += 1
            continue

        topics = buckets.get(domain, {})
        # Ordered as the rules are, so a domain hub reads in a deliberate
        # sequence rather than alphabetically by accident.
        order = [t for t, _, _ in RULES[domain] if t in topics]
        order += [t for t in topics if t not in order]

        for topic in order:
            notes = sorted(topics[topic])
            title = topic.replace("-", " ").capitalize()
            lines = [f"- [[{s}|{t}]]" for t, s in notes]
            body = (frontmatter(title, ["moc", domain])
                    + f"# {title}\n\n{desc_for(domain, topic)}\n\n"
                    + f"{len(notes)} notes.\n\n" + "\n".join(lines)
                    + f"\n\nPart of [[moc-{domain}|{dom_title}]].\n")
            (VAULT / f"moc-{topic}.md").write_text(body, encoding="utf-8")
            made += 1

        lines = [f"- [[moc-{t}|{t.replace('-', ' ').capitalize()}]] — {len(topics[t])} notes"
                 for t in order]
        total = sum(len(v) for v in topics.values())
        body = (frontmatter(dom_title, ["moc", domain])
                + f"# {dom_title}\n\n{dom_desc}\n\n{total} notes across "
                + f"{len(order)} topics.\n\n" + "\n".join(lines)
                + "\n\nBack to [[index|Index]].\n")
        (VAULT / f"moc-{domain}.md").write_text(body, encoding="utf-8")
        made += 1

    idx = (frontmatter("Index", ["orb", "moc"])
           + "# Index\n\nThe vault, from the top. Every note is reachable from "
             "here in three hops: domain, topic, note.\n\n"
           + "\n".join(f"- [[moc-{d}|{t}]] — {dd}" for d, t, dd in DOMAINS)
           + "\n")
    (VAULT / "index.md").write_text(idx, encoding="utf-8")

    print(f"  hub notes written: {made} (+ index)")
    for domain, dom_title, _ in DOMAINS:
        if domain == "orb":
            print(f"  {dom_title:24} {len(orb):3} notes")
            continue
        topics = buckets.get(domain, {})
        print(f"  {dom_title:24} {sum(len(v) for v in topics.values()):3} notes / {len(topics)} topics")
        for t in sorted(topics, key=lambda k: -len(topics[k])):
            print(f"      {t:28} {len(topics[t]):3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
