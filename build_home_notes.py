"""A broader base: home systems, money, security, DIY, health, garden, travel.

Written into measured gaps again rather than guessed at. Before this the vault
had: RCD 0, plug wiring 0, descaling 0, scams 0, two-factor 0, wall fixings 0,
timber 0, bicycle 0, dental 0, ibuprofen 0, paracetamol 0, pruning 0, visa 0,
jet lag 0.

Same discipline as the other build_*_notes scripts: written directly, dense
enough to survive a 900-character excerpt, and nothing stated that I am not
confident of. Doses and electrical figures are the two categories where a
wrong note does real harm, so both say what they are and where the authority
lies - the BNF and the patient information leaflet for one, Part P and a
qualified electrician for the other.

    python3 build_home_notes.py [vault-dir]
"""
import datetime
import pathlib
import re
import sys

VAULT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/orb/mem")

NOTES = [
    # ------------------------------------------------------------ electrics
    ("UK plug wiring and fuse ratings", ["ref", "electrical", "uk"], """
| Wire         | Colour        | Terminal          |
|--------------|---------------|-------------------|
| Live         | Brown         | L, right, fused   |
| Neutral      | Blue          | N, left           |
| Earth        | Green/yellow  | E, top centre     |

Pre-1977 cable used red for live and black for neutral. If you meet those,
treat the whole installation as old and have it inspected.

Fuse in the plug protects the FLEX, not the appliance:

| Fuse | Suitable for                                    |
|------|-------------------------------------------------|
| 3 A  | Up to about 700 W - lamps, radios, laptops      |
| 5 A  | Uncommon; some older appliances                 |
| 13 A | Above 700 W - kettles, heaters, washing machines |

Fitting 13 A where 3 A belongs means a fault can heat the flex badly before the
fuse ever notices. Fitting 3 A where 13 A belongs simply blows.

The earth wire is left longest on purpose: if the cord is yanked, live and
neutral pull free before earth does.
"""),

    ("RCDs, MCBs and what actually protects you", ["ref", "electrical", "uk"], """
Two different devices doing two different jobs, and only one of them is about
you.

MCB - Miniature Circuit Breaker. Protects the CABLE from overload and short
circuit. Rated in amps: 6 A lighting, 32 A ring main, 40 A shower. It will
happily let a fatal current pass through a person.

RCD - Residual Current Device. Compares current flowing out against current
returning. A difference means it is going somewhere else - through you, or to
earth. Trips at around 30 mA in tens of milliseconds. This is the one that
saves lives.

RCBO combines both in one module.

Test RCDs with the test button roughly every three months. An RCD that has sat
untested for years may be seized.

A tripping RCD means a real fault somewhere. Repeatedly resetting it without
finding out why is the electrical equivalent of taping over a warning light.

Fixed wiring work in a UK home is notifiable under Part P. Replacing a fuse or
a plug is not; adding a circuit is.
"""),

    # ------------------------------------------------------------- heating
    ("Boiler pressure and bleeding radiators", ["ref", "home"], """
Combi boiler pressure, cold: typically 1.0 - 1.5 bar. It rises when hot, which
is normal. Below about 0.8 the boiler will usually lock out.

Repressurising: find the filling loop - a braided hose with a valve at each end
under the boiler. Open both slowly, watch the gauge, close them at 1.2 bar.
Leaving it open over-pressurises and dumps water out of the safety valve.

Bleeding a radiator - do this when the top is cold and the bottom hot, which
means trapped air:
1. Turn the heating OFF and let it cool
2. Radiator key on the bleed valve, quarter turn anticlockwise
3. Hiss, then a dribble of water - close it immediately
4. Check boiler pressure afterwards; bleeding drops it

Bleed the downstairs radiators first, then upstairs.

Pressure that keeps falling means a leak somewhere - often the safety valve
outside, or a slow weep at a joint. Repeated topping up is a symptom, not a
fix, and it introduces fresh oxygenated water that corrodes the system.
"""),

    ("Limescale and descaling", ["ref", "home"], """
Scale is calcium carbonate from hard water. Wales and much of the west is soft
to moderate; the south and east of England is hard.

What works: acid. Citric acid powder (about 30 g in a kettle of water), white
vinegar, or a proprietary descaler. Boil, leave 30 minutes to an hour, rinse
thoroughly, boil once more and discard.

Kettles: descale when the element looks furred, not on a schedule. Scale is an
insulator, so a furred element uses measurably more electricity.

Shower heads: unscrew and soak, or bag vinegar around it overnight with an
elastic band.

Do NOT use acid descaler on aluminium, or on chrome plating for long periods.
And never mix descaler with bleach - acid plus hypochlorite releases chlorine
gas.

Steam irons and coffee machines usually specify a descaler; the manual's
instruction wins over the general method.
"""),

    # ------------------------------------------------------- money & scams
    ("How to tell a scam from your bank", ["ref", "money", "security"], """
The single reliable rule: a genuine bank will NEVER ask you to move money to a
"safe account". No exceptions. That request is definitionally a scam.

Nor will they ask for:
- Your full PIN or password
- A one-time code read out over the phone
- Remote access to your computer

Common shapes:
- Number spoofing - the caller ID shows your bank's real number. Caller ID can
  be forged trivially and proves nothing.
- Text with a link about a missed delivery, unpaid toll, or account problem
- "Your account is compromised, act now" - urgency is the tool
- WhatsApp from an unknown number claiming to be your child with a new phone

What to do: hang up. Wait five minutes or use a different phone - a scammer can
hold the line open on a landline. Then ring the number on the back of your
card, or 159, which connects you to your bank directly.

Report to Action Fraud. If money has gone, tell the bank immediately - the
reimbursement rules for authorised push payment fraud have strengthened.
"""),

    ("Two-factor authentication: which kinds are worth it", ["ref", "security"], """
| Method            | Strength | Weakness                          |
|-------------------|----------|-----------------------------------|
| SMS code          | Weak     | SIM swap, interception            |
| Email code        | Weak     | Only as strong as the email account |
| Authenticator app (TOTP) | Good | Phone loss without backup codes |
| Push approval     | Good     | "MFA fatigue" - approving by reflex |
| Hardware key (FIDO2) | Best  | Cost; needs a backup key          |

TOTP is the six-digit rolling code from an app. It is generated on the device
from a shared secret and a clock, so it works offline and cannot be phished by
a fake SMS.

Hardware keys are the only method that resists phishing outright: the key
checks the site's real domain before responding, so a convincing fake gets
nothing.

Whatever you use, SAVE THE BACKUP CODES somewhere that is not the phone. The
commonest way people lose an account permanently is losing the second factor
with no recovery path.

Any 2FA beats none. SMS is weak and still enormously better than a password
alone.
"""),

    ("UK credit files: what they hold and who has them", ["ref", "money", "uk"], """
Three agencies, and they hold different data: Experian, Equifax, TransUnion. A
lender may check any one of them, so a clean file at one is not the whole
picture. All three must give you statutory access.

What matters most:
- Payment history - missed payments mark the file for 6 years
- Credit utilisation - how much of your available limit you use. Under 30
  percent is the usual guidance
- Length of history - closing an old account can hurt
- Applications - each hard search is recorded; several in a short window
  looks like distress
- Electoral roll registration - a surprisingly large factor

What is NOT on it: your salary, your savings, your council tax, or whether you
have ever been overdrawn without exceeding a limit.

There is no such thing as a "credit blacklist", and the score a free service
shows you is that service's own number, not the one a lender sees.

Check for errors and for accounts you do not recognise - an unfamiliar account
is how identity fraud first shows up.
"""),

    ("Pensions: the parts that matter early", ["ref", "money", "uk"], """
State pension: based on National Insurance record. Broadly 35 qualifying years
for the full new State Pension, 10 years minimum to get anything. Check your
record and forecast - gaps can sometimes be bought back, and there are
deadlines for doing so.

Workplace pension: auto-enrolment means contributions from you, your employer,
and tax relief. Opting out forfeits the EMPLOYER contribution, which is the
part that makes it worth having - it is deferred pay, not a deduction.

Tax relief means a basic-rate taxpayer's 80 pence becomes 1 pound in the pot.
Higher-rate taxpayers can often claim more through self-assessment, and many
never do.

Compounding is the whole argument for starting early: money in at 25 has forty
years to grow, money in at 45 has twenty. The difference is not double, it is
several times over.

Consolidating old pots can reduce fees, but check for guarantees on older
schemes before moving anything - some contain benefits worth far more than the
fee saving.
"""),

    # -------------------------------------------------------------- DIY
    ("Wall fixings: choose by wall, not by weight", ["ref", "diy"], """
Find out what the wall IS first - knock it. Solid sounds dead, plasterboard
sounds hollow.

SOLID (brick, block, concrete):
- Plastic plug plus screw. Drill with a MASONRY bit, hammer action on
- Match plug to screw: brown plug takes a 8-10 gauge screw, red takes 6-8
- Drill to the depth of the plug, blow the dust out, plug flush with the surface

PLASTERBOARD (hollow):
- Self-drive plasterboard plug - light loads, mirrors, small shelves
- Spring toggle or gravity toggle - heavy loads, spreads behind the board
- Hollow-wall anchor (Molly) - reusable, needs a setting tool
- A plastic plug on its own in plasterboard is not a fixing, it is a delay

Anything genuinely heavy - a TV bracket, a wall unit, a handrail - should reach
the STUD or the masonry behind. Find studs with a detector or by tapping;
they are usually at 400 or 600 mm centres.

Always check for cables and pipes before drilling. Cables run vertically and
horizontally from sockets and switches - not diagonally.
"""),

    ("Timber sizes: nominal versus actual", ["ref", "diy"], """
A "4 by 2" is not 4 inches by 2 inches. The nominal size is the rough-sawn
dimension BEFORE planing; the actual size is what you get.

| Nominal   | Actual (PAR, approx) |
|-----------|----------------------|
| 2 x 1     | 44 x 20 mm           |
| 3 x 2     | 69 x 44 mm           |
| 4 x 2     | 95 x 44 mm           |
| 6 x 2     | 145 x 44 mm          |
| 8 x 2     | 195 x 44 mm          |

PAR means Planed All Round. Rough-sawn is closer to nominal but not flat.

Sheet materials come in 2440 x 1220 mm (8 x 4 feet). Plywood, MDF and OSB are
sold in that size and in halves and quarters of it.

Buy timber slightly long and cut to fit. Buy sheet goods to a cutting plan -
the offcut you did not plan for is the one you pay for twice.

Check for bow and twist by sighting down the length in the yard. A board that
is not straight in the rack will not be straight in the job.
"""),

    ("Drill bits: which for what", ["ref", "diy"], """
| Bit            | For                  | Tell it apart by          |
|----------------|----------------------|---------------------------|
| HSS (twist)    | Metal, plastic, wood | Plain steel or black/gold |
| Masonry        | Brick, block, stone  | Wider tungsten tip        |
| Brad point     | Clean holes in wood  | Sharp centre spur         |
| Spade / flat   | Fast rough holes in wood | Flat paddle shape     |
| Hole saw       | Large holes          | Toothed cylinder          |
| Countersink    | Recess for screw head| Cone                      |

Masonry bits need HAMMER action; using hammer on wood or metal destroys both
the bit and the hole. Using an HSS bit on masonry blunts it in seconds.

Speed rule: big bit, slow speed. Small bit, fast. Metal wants slow and steady
with cutting fluid; wood wants faster; masonry wants hammer and patience.

Pilot holes stop wood splitting and stop screws snapping - drill to the screw's
CORE diameter, not the thread diameter, and to about the depth the screw will
reach.
"""),

    ("Bicycle: the M-check and chain wear", ["ref", "bike"], """
The M-check runs the shape of an M over the bike, so nothing is missed:

1. Front wheel - spin it, check for buckle, squeeze spokes, check quick release
2. Up to the bars - check stem bolts, bars turn freely, cables not snagging
3. Down to the bottom bracket - cranks with no side play, chain, chainrings
4. Up to the saddle - clamped, correct height, not rocking
5. Rear wheel - as the front, plus cassette and derailleur alignment

Then brakes: pads not worn past the line, levers do not reach the bar, cables
not frayed.

CHAIN WEAR is the cheap maintenance that saves expensive parts. A chain
stretches as its pins wear:
- Under 0.5 percent: fine
- 0.5 - 0.75 percent: replace the chain
- Over 0.75 percent (1 percent on some drivetrains): the chain has already
  worn the cassette, and a new chain alone will skip

A chain checker costs very little. Replacing a chain on time costs a fraction
of replacing a cassette and chainrings with it.

Tyre pressure is on the sidewall as a range. Lower for grip and comfort, higher
for rolling speed - and check weekly, because narrow tyres lose pressure fast.
"""),

    # ------------------------------------------------------------- health
    ("Paracetamol: dose and why overdose is different", ["ref", "medical"], """
Adult: 500 mg to 1 g, every 4 to 6 hours. Maximum 4 g in 24 hours - that is
eight 500 mg tablets, and no more.

The critical thing about paracetamol is that overdose does NOT feel like an
emergency. Someone may feel nearly normal for a day or more while liver damage
progresses, and by the time symptoms appear the treatment window is closing.
Any suspected overdose is an immediate hospital matter regardless of how well
the person seems.

The commonest accidental route is doubling up: paracetamol is in a great many
cold and flu remedies, and in co-codamol. Read what is IN a combination
product before taking anything alongside it.

Safe with ibuprofen - different mechanisms, and they can be alternated.

Lower maximum doses apply to low body weight, liver disease and heavy alcohol
use. The patient information leaflet and the BNF are the authorities; this note
is orientation, not a prescription.
"""),

    ("Ibuprofen: dose and who should avoid it", ["ref", "medical"], """
Adult, over the counter: 200 - 400 mg every 4 to 6 hours, maximum 1,200 mg in
24 hours. Higher doses exist on prescription.

Take with or just after food. It is an NSAID and irritates the stomach lining.

Avoid, or ask first, if you have:
- Stomach ulcers or a history of them
- Asthma - it triggers symptoms in a minority of asthmatics
- Kidney problems, heart failure, or uncontrolled high blood pressure
- Are pregnant, particularly the third trimester
- Are already on aspirin, warfarin or another NSAID

Dehydration matters: ibuprofen plus dehydration plus hard exercise is hard on
the kidneys, which is why it is a poor choice mid-endurance-event.

Works differently from paracetamol - anti-inflammatory as well as analgesic, so
better for swelling, sprains and dental pain. The two can be taken together or
alternated.

Authority is the leaflet and the BNF, not this note.
"""),

    ("Dental care: what actually works", ["ref", "medical"], """
Brush twice daily for two minutes with fluoride toothpaste, 1,350 - 1,500 ppm
fluoride for an adult.

Spit, do not rinse. Rinsing with water immediately washes away the fluoride
that is the point of the exercise. This is the single most commonly ignored bit
of dental advice.

Clean between the teeth daily - floss or interdental brushes. Brushing reaches
about three-fifths of the tooth surface; decay and gum disease start in the
bit it misses.

Do not brush straight after anything acidic - fruit, wine, fizzy drinks, or
vomiting. Enamel is temporarily softened and brushing abrades it. Wait an hour.

Bleeding gums are not normal and are not a reason to stop brushing there - they
are usually early gum disease, and the response is more careful cleaning, not
less.

Electric brushes outperform manual ones on plaque removal, mostly because they
enforce timing and technique.
"""),

    ("Rashes: the one that matters", ["ref", "medical", "emergency"], """
Most rashes are not urgent. One pattern is, and it is worth knowing by sight.

A NON-BLANCHING rash - one that does NOT fade when pressed - can indicate
meningococcal septicaemia. Press a clear glass firmly against it: if the marks
stay visible through the glass, treat it as an emergency.

Do not wait for a rash. In meningitis and septicaemia the rash is a LATE sign,
and many cases never develop one. The earlier signs matter more:
- Fever with cold hands and feet
- Severe headache, neck stiffness, dislike of bright light
- Drowsiness, confusion, difficulty waking
- In babies: a bulging fontanelle, high-pitched cry, floppiness
- Rapid breathing, mottled skin, severe limb pain

If someone is deteriorating quickly and you are worried, that alone is reason
enough to call 999. Trust the trajectory rather than any single sign.
"""),

    ("Sleep: what actually shifts it", ["ref", "wellbeing"], """
The two systems: sleep pressure, which builds the longer you are awake, and the
circadian clock, set mainly by light.

What works, in rough order of effect:
- Consistent WAKE time, seven days a week. The wake time anchors the clock; the
  bedtime follows
- Daylight within an hour of waking, outdoors, even when overcast
- No caffeine after early afternoon - its half-life is around 5 hours, so a 4pm
  coffee is still a quarter present at midnight
- Cool, dark, quiet room
- Get out of bed if awake more than about 20 minutes; lying there trains the
  bed as a place of frustration

What does not work as well as people think: alcohol, which shortens time to
sleep and wrecks the second half of the night; catching up at weekends, which
shifts the clock and makes Monday worse; and screens, which matter far less
than what you are doing on them.

Persistent insomnia has an effective non-drug treatment - CBT-I - which
outperforms sleeping tablets over the long run.
"""),

    # ------------------------------------------------------------- garden
    ("Pruning: when, by what the plant does", ["ref", "garden"], """
The general rule: prune spring-flowering shrubs AFTER they flower, and
summer-flowering ones in late winter or early spring.

Why: spring flowerers bloom on wood made LAST year, so a winter cut removes
this year's flowers. Summer flowerers bloom on THIS year's growth, so a winter
cut encourages exactly what you want.

| Plant                | When                          |
|----------------------|-------------------------------|
| Forsythia, philadelphus | Straight after flowering   |
| Buddleia, lavatera   | Late winter/early spring, hard |
| Roses (bush)         | Late winter, to an outward bud |
| Lavender             | After flowering, NOT into old wood |
| Apple, pear          | Winter, dormant               |
| Plum, cherry         | SUMMER only - winter pruning invites silver leaf |
| Hydrangea macrophylla| Spring, leaving old heads over winter for frost protection |

Cut just above an outward-facing bud, angled away from it. Remove the three Ds
first - dead, damaged, diseased - and then stand back before taking anything
else.

Never prune plum or cherry in winter. That one is a disease risk, not a
preference.
"""),

    ("Frost, hardiness and the last frost date", ["ref", "garden", "uk"], """
Ground frost and air frost are different: ground frost is commoner and can
occur when the air stays above zero.

Last frost in the UK varies enormously - coastal south-west may be frost-free
by April, inland and upland Wales can catch one into late May. Local knowledge
beats any national date.

Tender plants (tomatoes, courgettes, beans, dahlias) go out only after the last
expected frost, and want hardening off first: a week or two of increasing time
outdoors so they adapt to wind and cold.

Protection when a late frost is forecast: horticultural fleece, cloches, or
moving pots against a house wall. Watering the soil in the afternoon helps -
damp soil holds more heat than dry.

Frost pockets form where cold air drains downhill and collects, so the bottom of
a slope can be several degrees colder than halfway up it. Do not site a fruit
tree in one.
"""),

    # ------------------------------------------------------------- travel
    ("Travelling: health cover and jet lag", ["ref", "travel", "uk"], """
GHIC - the Global Health Insurance Card - replaced the EHIC for most UK
residents. It gives access to state-provided medically necessary healthcare in
the EU on the same terms as a local. It is free; any site charging for it is
not the official one.

What it is NOT: travel insurance. It does not cover repatriation, mountain
rescue, private treatment, or a cancelled trip. Take both.

Jet lag: roughly one day of adjustment per time zone crossed. Eastward is
harder than westward, because advancing the body clock is harder than delaying
it.

What helps:
- Light at the right time. Going east, seek morning light at the destination
  and avoid evening light. Going west, the reverse
- Shift to destination time the moment you board, including when you sleep
- Short flights of a few zones: often not worth adjusting at all

Alcohol and heavy meals on the flight make it worse, and dehydration in dry
cabin air amplifies everything.
"""),
]


def frontmatter(title, tags, now):
    return ("---\n"
            f"created: {now.isoformat(timespec='seconds')}\n"
            f"title: {title}\n"
            f"tags: [{', '.join(tags)}]\n"
            "source: written directly, not researched\n"
            "---\n\n")


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


def main():
    if not VAULT.is_dir():
        raise SystemExit(f"no vault at {VAULT}")
    now = datetime.datetime.now()
    written = skipped = 0
    for title, tags, body in NOTES:
        path = VAULT / f"{slug(title)}.md"
        if path.exists():
            skipped += 1
            continue
        path.write_text(frontmatter(title, tags, now) + f"# {title}\n" + body.rstrip() + "\n",
                        encoding="utf-8")
        written += 1
    print(f"  {written} written, {skipped} already present, {len(NOTES)} defined")
    print(f"  vault now: {len(list(VAULT.glob('*.md')))} notes")


if __name__ == "__main__":
    main()
