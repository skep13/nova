"""The things an assistant is actually asked, which the vault did not have.

The vault grew out of a search-and-rescue project and it shows: 1,057 reference
notes, and the measured coverage of ordinary life was refunds 0, warranty 0,
tenancy 0, driving 0, council 0, passport 0, unit conversions 0, postage 0,
defrosting 0. It knew HTTP status codes and not what to do when a washing
machine dies inside its guarantee.

Written directly rather than researched, like the other build_*_notes scripts,
and for the same reason: these are stable facts that survive being excerpted
into a 900-character window, and a scraped page makes a worse note than a
table.

UK throughout. Where a rule is genuinely in flux - private tenancy notice
periods are mid-reform - the note says so rather than stating a figure that
will quietly go stale. Nothing here is a substitute for advice on a
consequential decision, and the notes that touch law say what they are: the
shape of the rule, and the name of the thing to look up.

    python3 build_everyday_notes.py [vault-dir]
"""
import datetime
import pathlib
import re
import sys

VAULT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/orb/mem")

NOTES = [
    # ------------------------------------------------------ consumer rights
    ("Consumer Rights Act: faulty goods", ["ref", "consumer", "uk"], """
Goods must be of satisfactory quality, fit for purpose, and as described. The
remedy depends entirely on how long you have had them.

| When            | What you are entitled to                        |
|-----------------|-------------------------------------------------|
| First 30 days   | Short-term right to reject: full refund         |
| 30 days - 6 mth | One repair or replacement; if that fails, refund |
| After 6 months  | Same, but YOU must show the fault was there from the start |

In the first six months the burden of proof is on the RETAILER to show the item
was not faulty when sold. After six months it flips to you.

Your contract is with the retailer, not the manufacturer. "Contact the
manufacturer" is not a valid brush-off, though you may choose to.

A guarantee or warranty is IN ADDITION to these rights, never instead of them.
A shop saying "you only had a one-year warranty" has not answered the question
of whether the goods were of satisfactory quality - a washing machine failing
after 18 months arguably was not.

Claims are possible up to six years in England and Wales (five in Scotland),
though the older the item the harder the argument.
"""),

    ("Buying online: the 14-day cancellation right", ["ref", "consumer", "uk"], """
Distance selling gives a right to change your mind that shop purchases do not.

- 14 days from RECEIPT to notify the trader you are cancelling
- Then a further 14 days to send the goods back
- Refund due within 14 days of the trader getting them back
- No reason needs to be given, and the goods need not be faulty

You pay return postage unless the trader said otherwise or the item is faulty.
The trader must refund the standard outbound delivery cost, though not the
premium if you chose next-day.

Excluded: perishables, personalised or made-to-order items, sealed audio/video
or software once unsealed, and services you agreed to start immediately.

This is separate from and additional to your rights over faulty goods.
"""),

    # ----------------------------------------------------------- home admin
    ("Renting: deposits and notice", ["ref", "housing", "uk"], """
Deposit protection (England and Wales, assured shorthold tenancies): the
landlord must protect the deposit in a government-approved scheme within 30
days of receiving it, and give you the prescribed information. Failure can mean
a penalty of one to three times the deposit, and it can block a no-fault
eviction notice.

The three schemes are the Deposit Protection Service, MyDeposits, and the
Tenancy Deposit Scheme.

Deductions must be for actual loss - unpaid rent, damage beyond fair wear and
tear, cleaning to the standard at check-in. Not "wear and tear", and not
betterment: a landlord cannot charge for a new carpet because the old one was
old.

Notice periods for private tenancies are mid-reform and have changed more than
once recently. Check the current position rather than trusting a figure -
including this note.

Disputes go to the scheme's free adjudication service before any court.
"""),

    ("Council tax: bands, discounts and who pays", ["ref", "housing", "uk"], """
Bands A-H in England and Scotland, A-I in Wales, set on property value at a
fixed historic valuation date - 1991 in England and Scotland, 2003 in Wales.
The band reflects what the property was worth THEN, not now.

Reductions worth knowing:
- Single occupant: 25 percent off
- Everyone in the household a full-time student: exempt
- Severe mental impairment, or a live-in carer: possible disregard
- Empty and unfurnished: varies by council, and many now charge a premium
  rather than a discount

You can challenge your band, but the challenge can move it UP as well as down,
and it affects neighbours in identical properties.

Council tax is a priority debt: non-payment escalates faster and further than
most consumer debt, and the whole year's balance can become due at once.
"""),

    # ------------------------------------------------------------- vehicles
    ("Driving in the UK: the annual obligations", ["ref", "vehicles", "uk"], """
Three separate things, often confused, each with its own penalty:

| Thing     | When                                  | If you do not          |
|-----------|---------------------------------------|------------------------|
| MOT       | Annually, from the car's 3rd birthday | Fine; insurance may be void |
| Vehicle tax | Annually or monthly                 | Automatic penalty; clamping |
| Insurance | Continuous                            | Points, fine, seizure  |

Continuous Insurance Enforcement means a registered vehicle must be insured
even when parked and unused, unless you file a SORN - a Statutory Off Road
Notification.

You may drive an untaxed, un-MOT'd car ONLY to a pre-booked MOT test, and it
must still be insured.

An MOT is a snapshot of roadworthiness on the day, not a warranty. "It passed
its MOT last week" is not an answer to a fault found this week.
"""),

    ("Tyres: pressures, tread and age", ["ref", "vehicles"], """
| Item        | Requirement                                    |
|-------------|------------------------------------------------|
| Tread depth | 1.6 mm minimum across the centre 3/4, all round |
| Penalty     | 3 points and a fine PER TYRE                   |
| Pressure    | On a plate in the door shut or filler flap, NOT on the tyre |

The number moulded into the tyre sidewall is its MAXIMUM pressure, not the
recommended one. Use the vehicle manufacturer's figure.

Check pressures cold. A tyre warmed by ten miles of driving reads several PSI
high and will leave you under-inflated when it cools.

Age matters even with tread left: the four-digit DOT code gives week and year
of manufacture (3319 = week 33 of 2019). Rubber hardens with age; many
manufacturers advise replacement at around ten years regardless of wear.

The 20p test is a rough check - insert a 20p coin, and if the outer band is
visible the tread is near or below the limit.
"""),

    # ------------------------------------------------------------- kitchen
    ("Oven temperatures and gas marks", ["ref", "cooking"], """
| Gas | Celsius | Fan  | Fahrenheit | Description    |
|-----|---------|------|------------|----------------|
| 1/4 | 110     | 90   | 225        | Very cool      |
| 1/2 | 120     | 100  | 250        | Very cool      |
| 1   | 140     | 120  | 275        | Cool           |
| 2   | 150     | 130  | 300        | Cool           |
| 3   | 160     | 140  | 325        | Warm           |
| 4   | 180     | 160  | 350        | Moderate       |
| 5   | 190     | 170  | 375        | Moderately hot |
| 6   | 200     | 180  | 400        | Hot            |
| 7   | 220     | 200  | 425        | Hot            |
| 8   | 230     | 210  | 450        | Very hot       |
| 9   | 240     | 220  | 475        | Very hot       |

Fan ovens run roughly 20 C cooler than the dial for the same effect - so a
recipe saying 180 C means 160 C fan. Ignoring this is the commonest reason a
recipe burns.
"""),

    ("Food safety: temperatures and storage", ["ref", "cooking", "medical"], """
| Thing                      | Figure                       |
|----------------------------|------------------------------|
| Fridge                     | 0 - 5 C                      |
| Freezer                    | -18 C                        |
| Danger zone                | 8 - 63 C - limit time here   |
| Reheat to                  | 70 C for 2 minutes, throughout |
| Cooked leftovers, fridge   | Eat within 2 days            |
| Cool before refrigerating  | Within 1 - 2 hours           |

Defrost in the fridge, not on the worktop. A large joint can take 24 hours or
more; the outside sits in the danger zone long before the middle thaws if you
do it at room temperature.

Never refreeze something that has thawed, unless you cook it first - then you
may freeze the cooked dish.

Rice is the one people underestimate: Bacillus cereus spores survive cooking,
and reheating does not destroy the toxin they produce. Cool it fast, refrigerate
within an hour, eat within a day, reheat once.

"Use by" is a safety date and matters. "Best before" is quality and does not.
"""),

    ("Freezer times and what does not freeze", ["ref", "cooking"], """
Freezing at -18 C stops bacterial growth but does not kill anything, and does
not stop quality declining. Times below are for quality, not safety.

| Food                | Keeps about |
|---------------------|-------------|
| Mince, sausages     | 3 months    |
| Beef, lamb joints   | 6-12 months |
| Chicken, whole      | 12 months   |
| Oily fish           | 3 months    |
| White fish          | 6 months    |
| Bread               | 3 months    |
| Hard cheese, grated | 6 months    |
| Soups and stews     | 3 months    |

Does not freeze well: whole eggs in shell, cream and mayonnaise-based sauces
(they split), lettuce and cucumber (cell walls collapse), fried food (goes
soggy), and whole potatoes (grainy).

Freeze in portions you will actually use. Label with contents AND date - an
unlabelled bag becomes a mystery within a month and a bin item within three.
"""),

    # ------------------------------------------------------------ household
    ("Laundry symbols", ["ref", "household"], """
| Symbol                | Meaning                                  |
|-----------------------|------------------------------------------|
| Tub with number       | Max wash temperature in Celsius          |
| Tub with one bar      | Reduced agitation (synthetics)           |
| Tub with two bars     | Much reduced agitation (delicates/wool)  |
| Tub with hand         | Hand wash only                           |
| Tub crossed out       | Do not wash                              |
| Triangle              | Bleach allowed                           |
| Triangle with stripes | Non-chlorine bleach only                 |
| Triangle crossed out  | Do not bleach                            |
| Square with circle    | Tumble dry                               |
| ...one dot            | Low heat                                 |
| ...two dots           | Normal heat                              |
| ...crossed out        | Do not tumble dry                        |
| Iron with dots        | 1 dot 110 C, 2 dots 150 C, 3 dots 200 C  |
| Circle                | Dry clean                                |
| Circle crossed out    | Do not dry clean                         |

The temperature on the label is a MAXIMUM, not an instruction. Washing cooler
saves energy and is usually gentler; it is worse only where you need to kill
something, such as towels or bedding after illness.
"""),

    ("Stain removal by type", ["ref", "household"], """
The governing rule: cold water for protein, hot for grease, and always blot
rather than rub - rubbing drives it into the fibre and spreads the edge.

| Stain           | Approach                                        |
|-----------------|-------------------------------------------------|
| Blood           | COLD water immediately. Hot water cooks the protein in |
| Red wine        | Blot, cover in salt to draw it out, then cold wash |
| Grease, oil     | Washing-up liquid directly on it, then hottest wash the fabric allows |
| Tea, coffee     | Rinse from the BACK of the fabric, cold          |
| Ink             | Dab with surgical spirit under an absorbent cloth |
| Grass           | Surgical spirit, then normal wash                |
| Sweat/deodorant | White vinegar soak before washing                |
| Candle wax      | Freeze, crack off, then iron between paper       |
| Rust            | Lemon juice and salt, in sunlight if possible    |

Never tumble-dry something still stained. Heat sets almost anything permanently,
and the second attempt is much harder than the first.
"""),

    # ----------------------------------------------------------- conversion
    ("Unit conversions worth knowing", ["ref", "conversion"], """
| From           | To            | Multiply by |
|----------------|---------------|-------------|
| inches         | mm            | 25.4        |
| feet           | metres        | 0.3048      |
| miles          | km            | 1.609       |
| yards          | metres        | 0.9144      |
| ounces         | grams         | 28.35       |
| pounds (lb)    | kg            | 0.4536      |
| stone          | kg            | 6.35        |
| pints (UK)     | litres        | 0.568       |
| gallons (UK)   | litres        | 4.546       |
| fl oz (UK)     | ml            | 28.4        |
| psi            | bar           | 0.0689      |
| horsepower     | kW            | 0.7457      |
| lb-ft (torque) | Nm            | 1.356       |

Celsius to Fahrenheit: multiply by 9/5, add 32. Back: subtract 32, times 5/9.
-40 is the same in both, which is a useful sanity check.

UK and US measures differ: a UK pint is 568 ml, a US pint 473 ml. A UK gallon
is 4.546 litres, a US gallon 3.785. Recipes and fuel figures are wrong by a
fifth if you take the wrong one.
"""),

    ("Cooking measures: cups, spoons and the US problem", ["ref", "cooking", "conversion"], """
| Measure       | Metric  |
|---------------|---------|
| 1 US cup      | 240 ml  |
| 1 UK teacup   | 280 ml (rare in modern recipes) |
| 1 tablespoon (UK/US) | 15 ml |
| 1 teaspoon    | 5 ml    |
| 1 Australian tablespoon | 20 ml - the odd one out |

Cups measure VOLUME, so a cup of flour and a cup of sugar are different weights.
This is the single biggest source of error in US recipes:

| Ingredient (1 US cup) | Weight  |
|-----------------------|---------|
| Plain flour           | 120 g   |
| Granulated sugar      | 200 g   |
| Brown sugar, packed   | 220 g   |
| Butter                | 227 g   |
| Rice, uncooked        | 185 g   |
| Rolled oats           | 90 g    |

Weigh where you can. Scooping flour with a cup compacts it and can add 20
percent without you noticing, which is why the same recipe works for one person
and not another.
"""),

    # ----------------------------------------------------------- post & time
    ("Royal Mail sizes and what they cost you", ["ref", "post", "uk"], """
Price is driven by size first and weight second - a light but bulky parcel
costs more than a heavy flat one.

| Format        | Max dimensions        | Max weight |
|---------------|-----------------------|------------|
| Letter        | 240 x 165 x 5 mm      | 100 g      |
| Large letter  | 353 x 250 x 25 mm     | 750 g      |
| Small parcel  | 450 x 350 x 160 mm    | 2 kg       |
| Medium parcel | 610 x 460 x 460 mm    | 20 kg      |

The 25 mm depth on a large letter is the one that catches people: an item that
fits the length and width goes up a whole price band if it is a centimetre too
thick. Postboxes have a slot gauge for exactly this.

Proof of postage is free at a Post Office counter and is not the same as
tracking. For anything valuable, tracked or signed-for is what gives you a
claim.

Prices change annually - check current rates rather than trusting a figure.
"""),

    ("UK time, BST and writing dates unambiguously", ["ref", "time", "uk"], """
The UK is on GMT (UTC+0) in winter and BST (UTC+1) in summer.

- Clocks go FORWARD one hour at 01:00 on the last Sunday in March
- Clocks go BACK one hour at 02:00 on the last Sunday in October
- "Spring forward, fall back"

The 01:00-02:00 window on the October Sunday happens twice, which is why
scheduled jobs in that hour can run twice or not at all. Servers should run in
UTC for exactly this reason.

Writing dates: 03/09/2026 is 3 September in the UK and 9 March in the US. The
unambiguous forms are:
- ISO 8601: 2026-09-03 - sorts correctly as text, no ambiguity, use this
- Written month: 3 September 2026

ISO also defines times: 2026-09-03T14:30:00Z, where Z means UTC.
"""),

    # ------------------------------------------------------------- identity
    ("UK passports and travel documents", ["ref", "admin", "uk"], """
An adult passport is valid for 10 years, a child's for 5.

The rule that catches people travelling to the EU: since Brexit, a UK passport
must be

- issued less than 10 years before the date you ENTER, and
- valid for at least 3 months after the date you intend to LEAVE

Extra months carried over from an old renewal no longer count towards the first
test. A passport showing a valid expiry date can still be refused.

Renewals take longer at peak times, and the passport must usually be sent away.
Check the current published processing time before booking anything
non-refundable.

Some countries require six months' validity, which is stricter than the EU
rule. The destination's requirement always wins.
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
