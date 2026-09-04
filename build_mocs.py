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

import vaultpaths

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
    "code": [
        ("languages", "The languages themselves, and what each is for.",
         ["programming language", "python", "shell script", "bash", "javascript",
          "c (programming", "rust", "go (programming"]),
        ("testing-and-debugging", "Finding out that it is wrong, and finding out why.",
         ["debugging", "software bug", "unit testing", "test-driven",
          "regression testing", "code review", "technical debt", "refactoring",
          "logging", "memory leak", "race condition"]),
        ("writing-code", "The constructs every language argues about differently.",
         ["object-oriented", "functional programming", "recursion", "variable",
          "data type", "type system", "pointer", "memory management",
          "exception handling", "callback", "serialization", "idempotence",
          "defensive programming", "design pattern"]),
        ("tools-and-formats", "Everything around the code: building it, shipping it, reading it.",
         ["application programming interface", "library", "framework",
          "package manager", "integrated development", "vim", "json", "xml",
          "yaml", "character encoding", "command-line", "environment variable",
          "exit status", "standard streams", "pipeline", "make (", "linker",
          "bytecode", "versioning", "documentation", "algorithm",
          "parallel computing", "asynchronous", "fail-safe"]),
    ],
    "ops": [
        ("reliability", "Designing for the day something breaks, because it will.",
         ["high availability", "fault tolerance", "redundancy",
          "single point of failure", "mean time between", "service-level",
          "chaos engineering"]),
        ("deployment", "Getting a change into production without taking it down.",
         ["continuous deployment", "rollback", "blue-green", "canary",
          "infrastructure as code", "configuration management",
          "capacity planning"]),
        ("running-systems", "The day-to-day of keeping machines alive and observable.",
         ["proxmox", "os-level virtualization", "cgroups", "file-system permissions",
          "iptables", "log file", "network monitoring", "system administrator",
          "root cause", "postmortem", "runbook", "observability", "telemetry",
          "time synchronization", "network time protocol", "public key certificate"]),
    ],
    "wellbeing": [
        ("mental-health", "Conditions, what they are, and what helps.",
         ["depress", "anxiety", "bipolar", "obsessive", "panic", "phobia",
          "post-traumatic", "attention deficit", "autism", "eating disorder",
          "seasonal affective", "suicide", "addiction", "substance"]),
        ("therapy-and-coping", "Ways through: professional, practical and personal.",
         ["psychotherapy", "counseling", "counselling", "serotonin", "coping",
          "resilience", "sleep hygiene", "motivational interviewing",
          "group psychotherapy", "assertiveness"]),
        ("feelings-and-people", "Emotions, and the relationships they happen in.",
         ["loneliness", "grief", "empathy", "compassion", "forgiveness",
          "gratitude", "happiness", "well-being", "emotion", "anger", "fear",
          "shame", "trust", "friendship", "social support", "interpersonal",
          "burnout", "work"]),
    ],
    "culture": [
        ("music", "Sound organised on purpose.",
         ["music", "notation", "rhythm", "harmony", "melody", "jazz", "guitar",
          "piano", "orchestra"]),
        ("film-and-image", "Pictures, moving and still.",
         ["film", "cinemato", "editing", "screenwriting", "documentary",
          "animation", "photography", "composition", "color theory", "painting",
          "sculpture", "graphic design", "typography", "drawing"]),
        ("words-and-belief", "Stories people tell, and what they believe.",
         ["literature", "novel", "poetry", "shakespeare", "mythology", "folklore",
          "religion", "christianity", "islam", "buddhism", "hinduism", "judaism",
          "aesthetics", "theatre"]),
        ("play-and-places", "Games, and where culture is kept.",
         ["chess", "board game", "video game", "museum", "dance", "architecture"]),
    ],
    "nature": [
        ("animals", "What moves, and how it lives.",
         ["animal", "mammal", "bird", "fish", "insect", "reptile", "amphibian",
          "dog", "cat", "horse", "bee", "butterfly", "spider", "migration",
          "hibernation", "nocturnality", "camouflage"]),
        ("plants-and-fungi", "What grows.",
         ["tree", "flower", "fungus", "moss", "seed", "pollination", "soil"]),
        ("weather-and-land", "The sky, the water and the ground.",
         ["weather", "cloud", "rain", "snow", "thunderstorm", "wind", "tide",
          "river", "mountain", "forest", "desert", "wetland", "coral"]),
        ("ecology", "How all of it fits together, and what is being lost.",
         ["biodiversity", "extinction", "conservation"]),
    ],
    "skills": [
        ("communicating", "Getting an idea from your head into someone else's.",
         ["public speaking", "writing", "note-taking", "reading", "typing",
          "language acquisition", "translation", "sign language", "braille",
          "handwriting", "speed reading"]),
        ("making-and-mending", "Doing things with your hands.",
         ["knot", "sewing", "knitting", "woodworking", "carpentry", "baking",
          "home repair", "cleaning", "origami"]),
        ("moving-and-outdoors", "Sport, and getting about outside.",
         ["swimming", "running", "cycling", "yoga", "orienteering", "camping",
          "hiking", "fishing", "climbing", "juggling"]),
        ("remembering", "Techniques for holding on to things.",
         ["memory technique", "method of loci"]),
    ],
    "nova": [
        ("how-it-works", "The prose: architecture, failure modes, recovery.",
         ["nova architecture", "nova endpoints", "nova agents", "nova vault",
          "nova retrieval", "nova research", "nova backups", "nova health",
          "nova voice", "nova deploying", "nova recovery", "nova design",
          "orb "]),
        ("source-router", "remote_proxy.py: routing, retrieval, research, health.",
         ["remote_proxy"]),
        ("source-config", "How requests are routed and services are declared.",
         ["nginx.conf", "docker-compose"]),
        ("source-tools", "The watcher, the sandbox and the backup.",
         ["nova-maintain", "sandbox_server", "orb-backup"]),
    ],
    "web": [
        ("python-tooling", "The current Python stack, as it actually is rather than as the archive remembers.",
         ["uv ", "uv(", "ruff", "polars", "duckdb", "fastapi", "pydantic", "httpx",
          "textual", "rich", "typer", "pytest", "sqlalchemy"]),
        ("ai-runtimes", "Running models locally, and the formats they come in.",
         ["llama.cpp", "ollama", "vllm", "gguf", "pytorch", "transformers",
          "model context protocol"]),
        ("javascript-and-web", "The browser side, which moves fastest of all.",
         ["vite", "bun", "deno", "htmx", "tailwind", "typescript"]),
        ("infrastructure-tools", "Serving, proxying, deploying and watching.",
         ["podman", "caddy", "traefik", "prometheus", "grafana", "ansible",
          "opentofu", "terraform"]),
        ("data-formats-and-stores", "Where the data actually sits.",
         ["parquet", "arrow", "sqlite", "postgres"]),
    ],
    "kitchen": [
        ("techniques", "Heat, and what it does to food.",
         ["roasting", "frying", "boiling", "steaming", "grilling", "baking",
          "braising", "poaching", "stir fry", "marination", "meal preparation"]),
        ("ingredients", "The things themselves.",
         ["rice", "pasta", "bread", "egg", "potato", "spice", "herb", "butter",
          "olive oil", "vinegar", "salt", "sugar", "chocolate", "cheese",
          "yogurt", "yeast", "gluten", "sourdough", "stock", "sauce", "soup",
          "salad", "seasoning"]),
        ("equipment-and-keeping", "Tools, and making food last.",
         ["knife", "cutting board", "cookware", "oven", "microwave",
          "slow cooker", "pressure cooking", "preservation", "canning",
          "pickling", "freezing", "leftovers"]),
    ],
    "household": [
        ("heating-and-water", "Keeping the place warm and the water moving.",
         ["heat pump", "boiler", "radiator", "thermostat", "air conditioning",
          "ventilation", "glazing", "drain", "sink", "toilet", "shower",
          "water heating"]),
        ("electrics-and-safety", "The parts that hurt you if ignored.",
         ["fuse", "circuit breaker", "residual-current", "light fixture",
          "light bulb", "smoke detector", "carbon monoxide", "fire extinguisher"]),
        ("repair-and-decorating", "Fixing and finishing.",
         ["paint", "wallpaper", "tile", "grout", "sealant", "silicone", "screw",
          "nail", "drill", "hammer", "saw", "spirit level", "tape measure",
          "sandpaper", "varnish"]),
        ("things-going-wrong", "Damp, rot, rust and the rest of entropy.",
         ["rust", "limescale", "condensation", "mold", "damp", "woodworm"]),
        ("appliances", "The machines that do the chores.",
         ["washing machine", "dishwasher", "refrigerator", "vacuum cleaner"]),
    ],
    "garden": [
        ("growing", "Getting plants to appear and keep going.",
         ["tomato", "vegetable", "fruit", "seedling", "germination", "perennial",
          "annual", "bulb", "grafting", "growing season", "crop rotation",
          "companion planting"]),
        ("soil-and-feeding", "What plants are standing in.",
         ["mulch", "fertilizer", "compost", "soil ph", "irrigation"]),
        ("keeping-it-in-order", "Cutting back, and what turns up uninvited.",
         ["pruning", "weed", "pest", "greenhouse", "lawn", "hedge", "frost"]),
    ],
    "sport": [
        ("team-games", "Played in numbers.",
         ["association football", "offside", "rugby", "cricket", "basketball"]),
        ("individual-sport", "Played alone or one against one.",
         ["tennis", "golf", "athletics", "marathon", "boxing", "martial arts",
          "snooker", "darts", "formula one", "cycling", "olympic"]),
        ("training-and-injury", "Preparing, and recovering.",
         ["sports injury", "warming up", "stretching", "physical therapy",
          "sportsmanship"]),
    ],
    "everyday": [
        ("the-body-being-odd", "Small physical things with real explanations.",
         ["jet lag", "sunburn", "sunscreen", "hiccup", "yawn", "sneeze",
          "blister", "bruise", "cramp", "dehydration", "hangover",
          "motion sickness", "snoring", "dandruff", "body odor", "halitosis",
          "hay fever", "insect bite", "splinter", "papercut", "burn",
          "common cold", "nail biting"]),
        ("weather-and-time", "Reckoning, and the sky.",
         ["heat wave", "static electricity", "time zone", "daylight saving",
          "leap year", "public holiday"]),
        ("dealing-with-people", "The unwritten rules.",
         ["queue", "tipping", "etiquette", "small talk", "handshake",
          "body language"]),
    ],
    "selfwork": [
        ("how-you-see-yourself", "The internal commentary, and its distortions.",
         ["impostor", "perfectionism", "introversion", "self-control",
          "delayed gratification", "self-care", "comparison", "envy", "regret"]),
        ("getting-things-done", "Turning intention into action.",
         ["goal setting", "burnout", "rumination", "overthinking", "boredom"]),
        ("with-other-people", "Saying the difficult thing well.",
         ["feedback", "active listening", "conflict resolution", "apology",
          "boundary"]),
        ("the-good-parts", "Not everything is a problem to manage.",
         ["curiosity", "awe", "humour", "play", "nostalgia"]),
    ],
    "home": [
        ("storage-and-data", "Disks, filesystems and the copies that survive them.",
         ["raid", "zfs", "btrfs", "network-attached", "solid-state", "hard disk",
          "s.m.a.r.t", "backup", "disaster recovery", "network file system", "samba"]),
        ("networking-and-access", "Getting traffic to the right box, from inside or out.",
         ["reverse proxy", "load balancing", "nginx", "dynamic dns", "port forwarding",
          "virtual lan", "wi-fi", "bluetooth", "network switch", "router",
          "power over ethernet", "wake-on-lan"]),
        ("servers-and-automation", "The machines themselves, and the jobs that keep them honest.",
         ["virtualization", "hypervisor", "systemd", "cron", "rsync", "syslog",
          "home automation", "mqtt", "zigbee", "raspberry pi", "single-board",
          "uninterruptible"]),
    ],
    "make": [
        ("printing-and-cad", "Turning a model on screen into an object on the bench.",
         ["3d printing", "fused filament", "stereolithography", "g-code",
          "computer-aided design", "polylactic", "acrylonitrile", "nylon", "adhesive"]),
        ("electronics", "Components, the laws they obey, and the tools that show you.",
         ["soldering", "printed circuit", "breadboard", "resistor", "capacitor",
          "inductor", "diode", "light-emitting", "transistor", "operational amplifier",
          "microcontroller", "arduino", "field-programmable", "multimeter",
          "oscilloscope", "ohm", "direct current", "alternating current", "battery",
          "lithium-ion", "pulse-width", "stepper", "servomotor"]),
        ("workshop-and-fabrication", "Cutting, joining and holding things together.",
         ["bearing", "screw thread", "torque", "welding", "machining",
          "injection", "laser cutting", "numerical control"]),
    ],
    "life": [
        ("food-and-kitchen", "Cooking, keeping food safe, and what is actually in it.",
         ["cooking", "food safety", "foodborne", "refrigeration", "fermentation",
          "bread", "coffee", "tea", "human nutrition"]),
        ("money-and-paperwork", "The admin that costs you if you ignore it.",
         ["personal finance", "compound interest", "interest rate", "inflation",
          "index fund", "pension", "insurance", "mortgage", "credit score",
          "income tax", "value-added", "budget", "contract", "consumer protection",
          "lease", "will and testament", "power of attorney"]),
        ("vehicles", "Keeping something on the road.",
         ["motor oil", "tire", "brake", "internal combustion", "electric vehicle",
          "bicycle"]),
        ("house-and-garden", "Maintaining the building you live in.",
         ["plumbing", "electrical wiring", "insulation", "central heating", "mold",
          "laundry", "recycling", "waste", "gardening", "compost"]),
    ],
    "health": [
        ("food-sleep-and-substances", "Inputs: what you eat, drink and how you rest.",
         ["vitamin", "protein", "carbohydrate", "fiber", "sleep", "circadian",
          "insomnia", "caffeine", "alcohol", "tobacco"]),
        ("fitness-and-the-body", "How the machine is built and how to keep it working.",
         ["exercise", "aerobic", "strength training", "stretching", "physical fitness",
          "body mass", "blood pressure", "cholesterol", "posture", "skin",
          "human eye", "hearing", "dentistry"]),
        ("illness-and-mental-health", "What goes wrong, and what helps.",
         ["diabetes", "immune", "vaccine", "antibiotic", "analgesic", "common cold",
          "influenza", "headache", "migraine", "allergy", "asthma", "mental health",
          "anxiety", "depressive", "stress", "meditation", "mindfulness"]),
    ],
    "mind": [
        ("thinking-and-bias", "How reasoning goes wrong, and how to check it.",
         ["cognitive bias", "confirmation bias", "critical thinking", "fallacy",
          "occam", "scientific method", "logic", "decision-making", "game theory",
          "prisoner", "intelligence"]),
        ("learning-and-habits", "Getting things into your head, and getting things done.",
         ["memory", "spaced repetition", "learning", "motivation", "habit",
          "procrastination", "attention", "flow", "time management", "creativity"]),
        ("psychology-and-philosophy", "What people are like, and how to live.",
         ["psychology", "emotional intelligence", "big five", "maslow",
          "conditioning", "cognitive behavioral", "philosophy", "ethics", "stoicism",
          "existentialism", "epistemology", "utilitarianism", "free will",
          "consciousness", "rhetoric", "negotiation"]),
    ],
    "world": [
        ("history", "How the present got here.",
         ["ancient", "middle ages", "renaissance", "enlightenment",
          "industrial revolution", "world war", "cold war", "space race"]),
        ("society-and-economy", "Institutions, money and the rules everyone runs on.",
         ["globalization", "united nations", "european union", "united kingdom",
          "democracy", "constitution", "rule of law", "human rights", "capitalism",
          "socialism", "economics", "supply and demand", "gross domestic",
          "central bank", "stock market", "cryptocurrency", "bitcoin"]),
        ("earth-and-energy", "The planet, and how it is powered.",
         ["climate", "renewable", "solar power", "wind power", "nuclear power",
          "electrical grid", "agriculture", "public transport", "geography",
          "plate tectonics", "ocean", "atmosphere", "time zone", "calendar",
          "cartography"]),
    ],
    "sci": [
        ("mathematics", "The language the rest of it is written in.",
         ["mathematics", "algebra", "geometry", "calculus", "derivative", "integral",
          "probability", "statistics", "normal distribution", "standard deviation",
          "correlation", "prime number", "logarithm", "trigonometry", "measurement",
          "international system"]),
        ("physics", "Matter, energy and the rules they follow.",
         ["physics", "classical mechanics", "newton", "energy", "thermodynamics",
          "entropy", "electromagnetism", "light", "optics", "sound", "wave",
          "quantum", "relativity", "gravity"]),
        ("chemistry-and-materials", "What things are made of and how they react.",
         ["atom", "periodic table", "chemical bond", "acid", "chemical reaction",
          "redox", "organic chemistry", "polymer", "water"]),
        ("life-sciences", "Living systems, from a cell upward.",
         ["biology", "cell", "dna", "gene", "evolution", "natural selection",
          "photosynthesis", "bacteria", "virus", "ecosystem"]),
        ("astronomy", "Everything further away than the weather.",
         ["astronomy", "solar system", "star", "galaxy", "black hole"]),
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
    "wellbeing": ("wellbeing-general", "Mental health and emotional ground, uncategorised."),
    "culture": ("culture-general", "Arts and belief that did not fit a narrower topic."),
    "nature": ("nature-general", "The living world, uncategorised."),
    "skills": ("skills-general", "Practical skills that span the other groupings."),
    "nova": ("nova-general", "Nova itself, uncategorised."),
    "kitchen": ("kitchen-general", "Cooking that did not fit a narrower topic."),
    "household": ("household-general", "Around the house, uncategorised."),
    "garden": ("garden-general", "Growing things, uncategorised."),
    "sport": ("sport-general", "Sport that did not fit a narrower topic."),
    "everyday": ("everyday-general", "Ordinary life, uncategorised."),
    "selfwork": ("selfwork-general", "Working on yourself, uncategorised."),
    "web": ("web-general", "Live-sourced notes that did not fit a narrower topic."),
    "code": ("programming-general", "Programming ground that did not fit a narrower topic."),
    "ops": ("operations-general", "Running and maintaining systems, uncategorised."),
    "home": ("homelab-general", "Self-hosting ground that did not fit a narrower topic."),
    "make": ("workshop-general", "Making and building, uncategorised."),
    "life": ("life-general", "Practical everyday knowledge that spans the other groupings."),
    "health": ("health-general", "General health that did not fit a narrower topic."),
    "mind": ("mind-general", "Thinking and behaviour, uncategorised."),
    "world": ("world-general", "History, society and the planet, uncategorised."),
    "sci": ("science-general", "Science that did not fit a narrower topic."),
    "security": ("security-foundations", "The vocabulary the rest of the security notes assume."),
    "ai": ("ml-foundations", "The ideas every other AI note is built on top of."),
    "cs": ("computing-foundations", "General computing ground that did not fit a narrower topic."),
    "field": ("field-general", "Field craft that spans the other groupings."),
}

DOMAINS = [
    ("security", "Security", "Offensive and defensive security, cryptography and the standards around them."),
    ("ai", "AI and Machine Learning", "From linear regression to transformers, plus how models are evaluated and where they go wrong."),
    ("cs", "Computer Science", "Systems, networks, data structures and the tooling underneath everything else."),
    ("life", "Everyday Life", "Food, money, paperwork, the house and the car — the things that actually come up."),
    ("health", "Health and Body", "Nutrition, sleep, fitness, and what to do when something is wrong."),
    ("mind", "Mind and Thinking", "How reasoning fails, how learning works, and how to decide."),
    ("world", "World and Society", "History, institutions, economics and the planet."),
    ("sci", "Science and Maths", "The general scientific ground everything else stands on."),
    ("home", "Homelab and Infrastructure", "Storage, networking and the servers this assistant runs on."),
    ("make", "Making and Electronics", "3D printing, circuits and the workshop."),
    ("field", "Field and Outdoors", "Casualty care, environmental injury and navigation."),
    ("nova", "Nova Itself", "How this assistant is built, how it fails, and how to fix it \u2014 including its own source."),
    ("wellbeing", "Wellbeing", "Mental health, emotions, and the people around you."),
    ("culture", "Culture", "Music, film, art, writing, belief and games."),
    ("nature", "The Natural World", "Animals, plants, weather and the systems they sit in."),
    ("kitchen", "Cooking", "Techniques, ingredients and keeping food."),
    ("household", "Around the House", "Heating, water, electrics, repairs and the things that go wrong."),
    ("garden", "Garden", "Growing, feeding and keeping order."),
    ("sport", "Sport", "Games, training and injury."),
    ("everyday", "Everyday Things", "Small physical oddities, weather, time and the unwritten rules."),
    ("selfwork", "Working On Yourself", "How you see yourself, and how you deal with other people."),
    ("skills", "Skills", "Things worth being able to do."),
    ("web", "Current Tooling", "Fetched from the live web, because the offline archive is a snapshot and cannot know any of it."),
    ("code", "Programming", "Languages, testing, debugging and the craft of writing software."),
    ("ops", "Operations", "Running systems: deployment, reliability, monitoring and recovery."),
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


# The hand-written cheatsheets are grouped by tag rather than by title keyword,
# and deliberately so. Keyword rules would scatter them: "Docker and Compose in
# practice" would land beside the encyclopedia article on containers, "cron and
# crontab" beside the one on job schedulers. That is the wrong neighbour. A
# lookup table and an explanation of the same subject are used at different
# moments, and someone reaching for the first does not want the second.
#
# The slug is scoped to the domain. Every other topic name in this file is
# hand-chosen and unique by inspection, but this one is generated for six
# domains at once, and hub files are written as a flat moc-<topic>.md — an
# unscoped name would have all six overwrite one file, leaving five domain hubs
# pointing at a list of someone else's notes. Silent, and only visible in the
# graph.
# A note is filed under the first of these tags it carries, so the ORDER is the
# priority: a note tagged both #ai and #security is security. The first block
# is the domain names themselves and is the original list, unchanged.
#
# The second block is aliases, and it exists because 40 notes were orphans.
# The note builders added since — money, home, everyday, field — tag by subject
# rather than by domain, so notes came through carrying #cooking, #consumer or
# #medical and matched nothing here at all. A tag that matches nothing means
# domain None, which means `continue`, which means the note is never written
# into a hub and hangs unreachable in the graph.
#
# Aliases come AFTER every real domain name, so they can only ever be a
# fallback: a note tagged [uk, sci] is still Science. Nothing that was being
# filed before is filed differently now.
DOMAIN_OF = {}
for _d, _, _ in DOMAINS:
    DOMAIN_OF[_d] = _d
DOMAIN_PRIORITY = list(DOMAIN_OF)

# tag -> the domain hub it belongs under. Kept consistent with the folder
# routing in build_folders.py, so the hub a note appears in and the directory
# it sits in tell the same story.
ALIASES = {
    "medical": "health",
    "emergency": "field",
    "cooking": "kitchen",
    # "Everyday Life" is described as food, money, paperwork, the house and
    # the car, which is precisely what this group of tags is.
    "money": "life", "consumer": "life", "work": "life", "housing": "life",
    "admin": "life", "uk": "life", "post": "life", "travel": "life",
    "vehicles": "life", "bike": "life", "security-personal": "life",
    "diy": "household", "tools": "household", "electrical": "household",
    "water": "household", "shelter": "household",
    "computing": "cs",
    "conversion": "everyday", "time": "everyday", "weather": "everyday",
    "rope": "skills", "words": "skills",
}
for _tag, _dom in ALIASES.items():
    if _tag not in DOMAIN_OF:
        DOMAIN_OF[_tag] = _dom
        DOMAIN_PRIORITY.append(_tag)

REFERENCE_SUFFIX = "-quick-reference"
REFERENCE_DESC = ("Lookup tables, flags and values — written to be consulted "
                  "mid-task rather than read.")
REFERENCE_TITLES = {
    "code": "Programming quick reference",
    "ops": "Operations quick reference",
    "cs": "Computing quick reference",
    "security": "Security quick reference",
    "make": "Workshop quick reference",
    "kitchen": "Kitchen quick reference",
    "sci": "Measurement quick reference",
}


def classify(title, domain, tags=()):
    # Keyed on "ref", not "reference": threat-model.md is tagged reference and
    # is prose, so the broader tag would file an essay among the cheatsheets.
    if "ref" in tags:
        return domain + REFERENCE_SUFFIX
    low = title.lower()
    for topic, _desc, keys in RULES.get(domain, []):
        if any(k in low for k in keys):
            return topic
    return FALLBACK[domain][0]


def desc_for(domain, topic):
    if topic.endswith(REFERENCE_SUFFIX):
        return REFERENCE_DESC
    for t, d, _ in RULES.get(domain, []):
        if t == topic:
            return d
    return FALLBACK[domain][1]


def topic_title(domain, topic):
    if topic.endswith(REFERENCE_SUFFIX):
        return REFERENCE_TITLES.get(domain, "Quick reference")
    return topic.replace("-", " ").capitalize()


def frontmatter(title, tags):
    return f"---\ncreated: {NOW}\ntitle: {title}\ntags: [{', '.join(tags)}]\n---\n\n"


def main():
    # Every write below goes through this. The vault is in folders, so
    # VAULT / "moc-security.md" no longer names the existing hub - it names a
    # new file that would collide with hubs/moc-security.md on basename, and
    # the embedding cache is keyed on basename. Resolved once: 1,502 notes is
    # a fast walk, but not one worth doing 141 times.
    here = vaultpaths.index(VAULT)

    tm = vaultpaths.find_note(VAULT, "threat-model.md", here)
    if not tm.exists():
        tm.write_text(THREAT_MODEL.format(now=NOW), encoding="utf-8")

    buckets = {}
    for p in sorted(vaultpaths.notes(VAULT)):
        if p.stem.startswith("moc-") or p.stem == "index":
            continue
        title, tags = read_meta(p)
        if "moc" in tags:
            continue
        domain = next((DOMAIN_OF[t] for t in DOMAIN_PRIORITY if t in tags), None)
        # Nova used to be diverted into a flat list here, which was right when
        # it held six notes and wrong now it holds 134 — most of them source
        # code, which belongs in its own topic rather than beside the prose that
        # describes it.
        if not domain:
            continue
        buckets.setdefault(domain, {}).setdefault(classify(title, domain, tags), []).append((title, p.stem))

    made = 0
    for domain, dom_title, dom_desc in DOMAINS:

        topics = buckets.get(domain, {})
        # Ordered as the rules are, so a domain hub reads in a deliberate
        # sequence rather than alphabetically by accident.
        order = [t for t, _, _ in RULES.get(domain, []) if t in topics]
        order += [t for t in topics if t not in order]
        # Reference first in every domain hub: it is the thing most often
        # wanted, and it is the only topic in the vault written rather than
        # derived, so it should not be buried under the encyclopedia.
        ref_topic = domain + REFERENCE_SUFFIX
        if ref_topic in order:
            order.remove(ref_topic)
            order.insert(0, ref_topic)

        for topic in order:
            notes = sorted(topics[topic])
            title = topic_title(domain, topic)
            lines = [f"- [[{s}|{t}]]" for t, s in notes]
            body = (frontmatter(title, ["moc", domain])
                    + f"# {title}\n\n{desc_for(domain, topic)}\n\n"
                    + f"{len(notes)} notes.\n\n" + "\n".join(lines)
                    + f"\n\nPart of [[moc-{domain}|{dom_title}]].\n")
            vaultpaths.find_note(VAULT, f"moc-{topic}.md", here).write_text(
                body, encoding="utf-8")
            made += 1

        lines = [f"- [[moc-{t}|{topic_title(domain, t)}]] — {len(topics[t])} notes"
                 for t in order]
        total = sum(len(v) for v in topics.values())
        body = (frontmatter(dom_title, ["moc", domain])
                + f"# {dom_title}\n\n{dom_desc}\n\n{total} notes across "
                + f"{len(order)} topics.\n\n" + "\n".join(lines)
                + "\n\nBack to [[index|Index]].\n")
        vaultpaths.find_note(VAULT, f"moc-{domain}.md", here).write_text(
            body, encoding="utf-8")
        made += 1

    idx = (frontmatter("Index", ["orb", "moc"])
           + "# Index\n\nThe vault, from the top. Every note is reachable from "
             "here in three hops: domain, topic, note.\n\n"
           + "\n".join(f"- [[moc-{d}|{t}]] — {dd}" for d, t, dd in DOMAINS)
           + "\n")
    # index.md is on build_folders' keep-at-root list, so this resolves to the
    # root either way - through find_note so it stays correct if that changes.
    vaultpaths.find_note(VAULT, "index.md", here).write_text(idx,
                                                             encoding="utf-8")

    print(f"  hub notes written: {made} (+ index)")
    for domain, dom_title, _ in DOMAINS:
        topics = buckets.get(domain, {})
        print(f"  {dom_title:24} {sum(len(v) for v in topics.values()):3} notes / {len(topics)} topics")
        for t in sorted(topics, key=lambda k: -len(topics[k])):
            print(f"      {t:28} {len(topics[t]):3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
