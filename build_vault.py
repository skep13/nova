"""Build a second-brain Obsidian vault from the offline Wikipedia.

Runs INSIDE LXC 101, where kiwix is reachable. For each topic it takes the
article's opening sections, strips them to prose, and writes a note with
frontmatter and tags.

The part that makes it a vault rather than a folder: once every note exists,
each is scanned for the titles of all the others and those mentions become
[[wikilinks]]. Sixty files in a directory is a folder; the same sixty with the
graph filled in is something you can actually think in. Doing it from the text
itself beats a hand-maintained relationship list, which would rot on the first
addition.

Hand-written notes are never touched. They still take part in the graph.
"""
import datetime, html, json, pathlib, re, sys, urllib.parse, urllib.request

MEM = pathlib.Path("/opt/orb/mem")
NOW = datetime.datetime.now().isoformat(timespec="seconds")
BASE = "http://localhost:8080/wiki"
BODY_CHARS = 3600          # several sections: retrieval excerpts a 900-char window

TOPICS = {
"ai": [
 "Artificial intelligence","Machine learning","Deep learning","Artificial neural network",
 "Transformer (deep learning architecture)","Attention (machine learning)",
 "Large language model","Foundation model","Word embedding","Backpropagation",
 "Gradient descent","Stochastic gradient descent","Overfitting","Regularization (mathematics)",
 "Convolutional neural network","Recurrent neural network","Long short-term memory",
 "Reinforcement learning","Q-learning","Reinforcement learning from human feedback",
 "Supervised learning","Unsupervised learning","Self-supervised learning","Transfer learning",
 "Knowledge distillation","Fine-tuning (deep learning)","Diffusion model",
 "Generative adversarial network","Autoencoder","Variational autoencoder",
 "Support vector machine","Random forest","Decision tree learning","Gradient boosting",
 "K-means clustering","K-nearest neighbors algorithm","Principal component analysis",
 "Linear regression","Logistic regression","Bayes' theorem","Naive Bayes classifier",
 "Perceptron","Multilayer perceptron","Activation function","Rectifier (neural networks)",
 "Softmax function","Cross-entropy","Loss function","Hyperparameter (machine learning)",
 "Feature engineering","Feature learning","Precision and recall","Confusion matrix",
 "Receiver operating characteristic","Cross-validation (statistics)","Bias–variance tradeoff",
 "Curse of dimensionality","Vanishing gradient problem","Batch normalization","Dropout (neural networks)",
 "Hallucination (artificial intelligence)","Prompt engineering","Retrieval-augmented generation",
 "Mixture of experts","Tokenization (lexical analysis)","Byte pair encoding","Perplexity",
 "Turing test","AI alignment","Explainable artificial intelligence","AI safety",
 "Natural language processing","Computer vision","Speech recognition","Named-entity recognition",
 "Sentiment analysis","Machine translation","Optical character recognition",
 "Expert system","Symbolic artificial intelligence","Genetic algorithm","Simulated annealing",
 "Markov decision process","Hidden Markov model","Monte Carlo tree search","A* search algorithm",
 "Gaussian process","Ensemble learning","Anomaly detection","Recommender system",
 "Federated learning","Edge computing","Neural architecture search","Attention Is All You Need",
],
"security": [
 "Computer security","Information security","Cryptography","Public-key cryptography",
 "Symmetric-key algorithm","Advanced Encryption Standard","RSA cryptosystem","Elliptic-curve cryptography",
 "Transport Layer Security","Cryptographic hash function","SHA-2","MD5",
 "Salt (cryptography)","Key derivation function","Bcrypt","Digital signature",
 "Public key infrastructure","X.509","Diffie–Hellman key exchange","Perfect forward secrecy",
 "Block cipher","Stream cipher","Block cipher mode of operation","Initialization vector",
 "Message authentication code","HMAC","End-to-end encryption","Pretty Good Privacy",
 "Buffer overflow","Stack buffer overflow","Heap overflow","Format string attack",
 "SQL injection","Cross-site scripting","Cross-site request forgery","Server-side request forgery",
 "Directory traversal attack","Privilege escalation","Race condition","Time-of-check to time-of-use",
 "Zero-day vulnerability","Common Vulnerabilities and Exposures","Common Vulnerability Scoring System",
 "Penetration test","Red team","Threat model","Attack surface","Kill chain",
 "Defense in depth (computing)","Principle of least privilege","Zero trust security model",
 "Malware","Ransomware","Rootkit","Trojan horse (computing)","Computer worm","Computer virus",
 "Spyware","Keystroke logging","Botnet","Command and control (malware)",
 "Phishing","Social engineering (security)","Denial-of-service attack","Man-in-the-middle attack",
 "Replay attack","ARP spoofing","DNS spoofing","IP address spoofing","Port scanner","Nmap",
 "Firewall (computing)","Intrusion detection system","Virtual private network","Proxy server",
 "Sandbox (computer security)","Virtual machine","Containerization (computing)",
 "Fuzzing","Reverse engineering","Static program analysis","Dynamic program analysis",
 "Disassembler","Debugger","Address space layout randomization","Executable-space protection",
 "Return-oriented programming","Shellcode","Exploit (computer security)","Metasploit Project",
 "Authentication","Multi-factor authentication","OAuth","OpenID Connect","JSON Web Token",
 "Kerberos (protocol)","Single sign-on","Access-control list","Role-based access control",
 "Side-channel attack","Timing attack","Spectre (security vulnerability)","Meltdown (security vulnerability)",
 "Password cracking","Rainbow table","Brute-force attack","Dictionary attack",
 "Security information and event management","Honeypot (computing)","Air gap (networking)",
 "Data breach","Digital forensics","Incident management","Chain of custody",
 "OWASP","National Institute of Standards and Technology","ISO/IEC 27001",
 "Tor (network)","Onion routing","Steganography","Certificate authority","Let's Encrypt",
],
"cs": [
 "Computer network","Internet protocol suite","Transmission Control Protocol","User Datagram Protocol",
 "Internet Protocol","IPv6","Domain Name System","Hypertext Transfer Protocol","HTTPS",
 "OSI model","Network address translation","Subnetwork","Routing","Border Gateway Protocol",
 "Secure Shell","File Transfer Protocol","WebSocket","Representational state transfer",
 "Operating system","Linux kernel","Process (computing)","Thread (computing)","Scheduling (computing)",
 "Virtual memory","Paging","File system","Inode","System call","Interrupt",
 "Deadlock","Mutual exclusion","Semaphore (programming)","Concurrency (computer science)",
 "Data structure","Array (data structure)","Linked list","Hash table","Binary search tree",
 "Heap (data structure)","Graph (abstract data type)","Trie","Big O notation",
 "Sorting algorithm","Quicksort","Merge sort","Binary search algorithm","Dynamic programming",
 "Breadth-first search","Depth-first search","Dijkstra's algorithm","Regular expression",
 "Finite-state machine","Compiler","Interpreter (computing)","Garbage collection (computer science)",
 "Database","Relational database","SQL","ACID","Database index","NoSQL",
 "Version control","Git","Continuous integration","Docker (software)","Kubernetes",
 "Public-key certificate","Base64","Unicode","UTF-8","Endianness","Floating-point arithmetic",
],
"field": [
 "Frostbite","Bone fracture","Choking","Cardiopulmonary resuscitation","First aid",
 "Navigation","Wind chill","Avalanche","Distress signal","Drowning","Snakebite",
 "Tick-borne disease","Burn","Sprain","Ordnance Survey National Grid","Mountain rescue",
 "Hyperthermia","Compass","Map reading","Survival skills","Hypoxia (medicine)",
],
}

HANDWRITTEN = {"Hypothermia","Bleeding","Shock","Heat illness","Dehydration",
               "Altitude sickness","Concussion"}


def get(url):
    try:
        return urllib.request.urlopen(url, timeout=45).read().decode("utf-8", "replace")
    except Exception:
        return ""


def find_article(title):
    s = get(BASE + "/search?books.filter.lang=eng&pattern="
            + urllib.parse.quote(title) + "&userlang=en")
    hits = re.findall(r'<a[^>]+href="([^"]*/content/[^"]*)"[^>]*>(.*?)</a>', s, re.S)
    for href, label in hits:
        lab = html.unescape(re.sub(r"<[^>]*>", "", label)).strip()
        if lab.lower() == title.lower():
            return href
    # Wikipedia often titles an article slightly differently from how it is
    # said; accept the top hit when it clearly contains the topic.
    for href, label in hits[:2]:
        lab = html.unescape(re.sub(r"<[^>]*>", "", label)).strip().lower()
        base = re.sub(r"\s*\(.*?\)\s*$", "", title).strip().lower()
        if base and base in lab:
            return href
    return None


def lede(href, limit=BODY_CHARS):
    art = get(BASE + href)
    if not art:
        return ""
    art = re.sub(r"(?is)<style.*?</style>", " ", art)
    art = re.sub(r"(?is)<script.*?</script>", " ", art)
    art = re.sub(r"(?is)<table.*?</table>", " ", art)
    paras, total = [], 0
    for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", art):
        p = html.unescape(re.sub(r"(?s)<[^>]+>", "", p))
        p = re.sub(r"\[\d+\]", "", p)
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) < 60:
            continue
        paras.append(p)
        total += len(p)
        if total > limit:
            break
    return "\n\n".join(paras)


def short(title):
    return re.sub(r"\s*\(.*?\)\s*$", "", title).strip()


def main():
    MEM.mkdir(parents=True, exist_ok=True)
    written, missing = {}, []
    total = sum(len(v) for v in TOPICS.values())
    n = 0
    for tag, titles in TOPICS.items():
        for t in titles:
            n += 1
            name = short(t)
            if name in HANDWRITTEN or name in written:
                continue
            href = find_article(t)
            body = lede(href) if href else ""
            if len(body) < 200:
                missing.append(t)
            else:
                fname = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] + ".md"
                written[name] = (fname, tag, t, body)
            if n % 25 == 0:
                print(f"  ... {n}/{total} ({len(written)} written)", flush=True)

    names = sorted(list(written) + list(HANDWRITTEN), key=len, reverse=True)
    for name, (fname, tag, source, body) in written.items():
        linked, used = body, set()
        for other in names:
            if other == name or other in used or len(other) < 6:
                continue
            pat = re.compile(r"(?<!\[)\b(" + re.escape(other) + r")\b(?!\])", re.I)
            m = pat.search(linked)
            if m:
                linked = linked[:m.start()] + "[[" + m.group(1) + "]]" + linked[m.end():]
                used.add(other)
        see = ", ".join(f"[[{u}]]" for u in sorted(used)[:10])
        doc = ("---\n" f"created: {NOW}\n" f"title: {name}\n"
               f"tags: [{tag}, reference]\n" f"source: wikipedia_en_full/{source}\n"
               "---\n\n" f"# {name}\n\n{linked}\n"
               + (f"\nSee also: {see}\n" if see else ""))
        (MEM / fname).write_text(doc, encoding="utf-8")

    by_tag = {}
    for name, (_, tag, _, _) in written.items():
        by_tag.setdefault(tag, []).append(name)
    print(f"\n  wrote {len(written)} notes")
    for tag, ns in sorted(by_tag.items()):
        print(f"    {tag:9} {len(ns)}")
    if missing:
        print(f"  not in the archive ({len(missing)}): " + ", ".join(missing[:15])
              + (" ..." if len(missing) > 15 else ""))
    json.dump(by_tag, open("/tmp/vault_tags.json", "w"))


main()
