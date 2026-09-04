"""Field reference for the gaps the vault actually had.

Counted rather than guessed. With 1,057 reference notes already in place, the
coverage of the things this device exists for was: radio 0, antenna 0,
casualty 0, river 0, water purification 0, shelter 0, knots 1, rope 1,
navigation 2. An assistant on a wrist in Welsh hills that knows HTTP status
codes and not the distress procedure has its priorities from the wrong project.

Written directly, like build_reference_notes.py, and for the same reasons:
these are stable facts that do not need a source round-trip, and a note built
as a compact table survives a 900-character excerpt window in a way prose does
not. Nothing is invented. Where a figure is jurisdiction-dependent it says so;
where I am not certain of a value it is left out, because a reference note that
is wrong is worse than one that is missing - and on this material, considerably
worse.

UK conventions throughout: OS grid, Ofcom licensing, BNF rather than US
prescribing, 999/112.

    python3 build_field_notes.py [vault-dir]
"""
import datetime
import pathlib
import re
import sys

VAULT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/orb/mem")

# (title, tags, body). Tags land in frontmatter and drive the hub layer; "field"
# is the one that matters, because search_vault ranks hand-written field notes
# above generated ones and these are the notes meant to win.
NOTES = [
    # ---------------------------------------------------------------- comms
    ("NATO phonetic alphabet", ["field", "comms"], """
A B C D E F: Alfa Bravo Charlie Delta Echo Foxtrot
G H I J K L: Golf Hotel India Juliett Kilo Lima
M N O P Q R: Mike November Oscar Papa Quebec Romeo
S T U V W X: Sierra Tango Uniform Victor Whiskey X-ray
Y Z:         Yankee Zulu

Numbers are spoken digit by digit. Nine is "niner" to avoid confusion with
German "nein" and with five over a poor link. Three is "tree", four "fower",
five "fife" in strict procedure; in UK civilian use plain English digits are
normal and understood.

Decimal point is "decimal". Thousands are spoken in full: 4500 is "fower five
zero zero", not "forty-five hundred".
"""),

    ("Radio prowords", ["field", "comms"], """
| Proword        | Meaning                                          |
|----------------|--------------------------------------------------|
| OVER           | I have finished, reply expected                  |
| OUT            | I have finished, no reply expected               |
| ROGER          | Received and understood                          |
| WILCO          | Received, understood, will comply                |
| SAY AGAIN      | Repeat your last                                 |
| I SAY AGAIN    | I am repeating                                   |
| WAIT           | Pause, under 5 seconds                           |
| WAIT OUT       | Pause, longer; I will call you back              |
| STANDBY        | Hold, I am dealing with something                |
| CORRECTION     | I made an error, what follows is correct         |
| READ BACK      | Repeat this message back to me                   |
| FIGURES        | Numbers follow                                   |
| SPELL          | Phonetic spelling follows                        |

"OVER AND OUT" is a contradiction and is not used. ROGER means heard, not
agreed - WILCO is the one that commits you to doing it.
"""),

    ("Distress, urgency and safety calls", ["field", "comms", "emergency"], """
Three levels, in descending priority. All are spoken three times.

MAYDAY - grave and imminent danger to life or vessel. Requires immediate
assistance.

PAN-PAN - urgency. A serious situation but not immediate danger to life;
someone injured but stable, a vehicle disabled in a hazardous place.

SECURITE (say "say-cur-i-tay") - safety. A navigational or weather warning.

Format after the call:
  1. MAYDAY x3
  2. "This is" + your callsign/name x3
  3. Position - grid reference or lat/long, or bearing and distance from a
     named landmark
  4. Nature of the emergency
  5. Assistance required
  6. Number of persons
  7. OVER

Marine VHF distress is channel 16. In the UK, 999 or 112 reaches the coastguard
and mountain rescue alike; ask for the service by name. 112 works on any
network including one you have no SIM for.
"""),

    ("PMR446 licence-free radio (UK)", ["field", "comms"], """
| Property        | Value                                       |
|-----------------|---------------------------------------------|
| Band            | 446.0 - 446.2 MHz, UHF                      |
| Channels        | 16 analogue (8 on older sets)               |
| Max power       | 500 mW ERP                                  |
| Antenna         | Integral only - external antennas not permitted |
| Licence         | None required in the UK                     |
| Realistic range | 0.5 - 2 km in terrain, more line-of-sight   |

UHF at half a watt does not follow valleys. Range in Welsh hills is line of
sight and little else: a ridge between you and the other set ends the
conversation regardless of how new the radio is. Height beats power every time.

Not compatible with marine VHF, PMR business radio, or amateur bands.
"""),

    ("UK VHF/UHF amateur bands", ["field", "comms"], """
| Band | Frequency        | Notes                                |
|------|------------------|--------------------------------------|
| 2 m  | 144 - 146 MHz    | Main VHF band, repeaters, SSB at low end |
| 70 cm| 430 - 440 MHz    | UHF, repeaters, more urban-friendly  |
| 6 m  | 50 - 52 MHz      | Sporadic-E openings in summer        |
| 4 m  | 70.0 - 70.5 MHz  | UK-specific allocation               |

A Foundation licence is the entry level in the UK and permits 25 W. Transmitting
on these bands without a licence is an offence; receiving is not.

2 m calling frequency is 145.500 MHz FM - make contact there, then move off it.
"""),

    # ------------------------------------------------------------- casualty
    ("Primary survey: catastrophic bleeding first", ["field", "medical", "emergency"], """
<C>ABCDE. The angle brackets are the point: catastrophic haemorrhage is dealt
with BEFORE airway, because someone can bleed to death faster than they can
suffocate.

<C> Catastrophic bleeding - direct pressure, pack the wound, tourniquet high
    and tight if a limb bleed will not stop
A   Airway - open it, head tilt chin lift, look in the mouth
B   Breathing - look, listen, feel for 10 seconds
C   Circulation - pulse, colour, capillary refill
D   Disability - AVPU: Alert, responds to Voice, responds to Pain, Unresponsive
E   Exposure - look for what you have not found yet, then keep them warm

Reassess after every intervention and after any move. A casualty who was fine
five minutes ago is not necessarily fine now.
"""),

    ("Catastrophic bleeding: pressure, packing, tourniquet", ["field", "medical", "emergency"], """
1. DIRECT PRESSURE, hard, with whatever is to hand. Most bleeding stops here.
2. If it soaks through, do not remove the first dressing - add on top and keep
   pressing.
3. WOUND PACKING for a junctional wound (groin, armpit, neck) where a
   tourniquet cannot go: push gauze firmly into the cavity, keep packing, then
   press for at least three minutes.
4. TOURNIQUET for a limb bleed that will not stop. High and tight, above the
   wound, over a single bone if possible. Tighten until the bleeding STOPS -
   an ineffective tourniquet that only occludes veins makes the bleeding worse.

Write the time of application on the casualty, visibly. Do not loosen it to
"let blood through" - that is an old teaching and it kills people. Once on, it
stays on until a clinician removes it.

An improvised tourniquet needs a windlass: a strap alone will not generate
enough pressure.
"""),

    ("Recovery position and CPR figures", ["field", "medical", "emergency"], """
Recovery position - for an unresponsive casualty who IS breathing normally:
roll toward you, top leg bent at 90 degrees, top hand under the cheek, head
tilted back to keep the airway open. Check breathing continuously.

CPR - unresponsive and NOT breathing normally:
| Element          | Adult                                   |
|------------------|-----------------------------------------|
| Compression rate | 100 - 120 per minute                    |
| Depth            | 5 - 6 cm                                |
| Ratio            | 30 compressions : 2 rescue breaths      |
| Hand position    | Centre of the chest, lower half of sternum |
| Recoil           | Full - let the chest come all the way back |

Compression-only CPR is acceptable and far better than nothing if you are
unwilling or unable to give breaths. Swap operator every two minutes; quality
falls off fast and the person doing it is the last to notice.

Agonal gasping is NOT normal breathing. It is a sign of cardiac arrest and CPR
should start.
"""),

    ("Hypothermia: recognition and rewarming", ["field", "medical"], """
| Stage    | Core temp   | Signs                                      |
|----------|-------------|--------------------------------------------|
| Mild     | 32 - 35 C   | Shivering, clumsy, "umbles" - stumbles, mumbles, fumbles, grumbles |
| Moderate | 28 - 32 C   | Shivering STOPS, confusion, drowsiness      |
| Severe   | below 28 C  | Unresponsive, rigid, pulse hard to find     |

Shivering stopping is not improvement. It is the single most important sign
that this is getting worse.

Handle a severely hypothermic casualty gently. Rough movement can trigger
ventricular fibrillation in a cold heart. Horizontal, insulated from the
ground, wind and wet removed, and shelter before anything else.

Rewarm the trunk, not the limbs - warming cold limbs first pushes cold blood
back to the core. No alcohol. No rubbing.

"Not dead until warm and dead": hypothermia is protective, and resuscitation
has succeeded from apparently hopeless states. Do not stop early on your own
judgement.
"""),

    # ----------------------------------------------------------- navigation
    ("OS grid references", ["field", "navigation"], """
| Digits | Precision | Example        |
|--------|-----------|----------------|
| 4-fig  | 1 km      | SO 21 14       |
| 6-fig  | 100 m     | SO 213 142     |
| 8-fig  | 10 m      | SO 2134 1421   |
| 10-fig | 1 m       | SO 21345 14213 |

Eastings before northings - "along the corridor, up the stairs". The two-letter
prefix names the 100 km square and must be given: a six-figure reference
without it repeats every 100 km.

Give mountain rescue a six-figure reference minimum, with the letters. Eight
figures if you can, but an accurate six beats a confidently wrong eight.
"""),

    ("Naismith's rule and its corrections", ["field", "navigation"], """
Base rule: 5 km/h on the flat, PLUS 1 minute for every 10 m of ascent.

  4 km with 300 m of ascent = 48 min + 30 min = 78 min

Corrections worth applying:
- Tranter's: adjusts for fitness and fatigue over a long day. A tired party in
  hour eight is not moving at hour-one pace.
- Descent: subtract nothing. Steep descent is often SLOWER than the flat, and
  hard on knees.
- Naismith assumes good conditions. Deep heather, bog, snow, night, or poor
  visibility can double it.

Plan on the rule, then add a contingency. Parties are overdue because the plan
was optimistic far more often than because something went wrong.
"""),

    ("Pacing and timing for navigation", ["field", "navigation"], """
Pacing counts DOUBLE paces (every time the same foot lands) over 100 m. Measure
your own on flat ground; do not use someone else's figure.

Typical adult: 60 - 70 double paces per 100 m on the flat.

Adjustments - all increase the count:
- Uphill, rough ground, deep heather, snow: more paces per 100 m
- Load carried: more
- Night, poor visibility: more

Timing is the cross-check. At 5 km/h, 100 m takes 72 seconds. Run pacing and
timing together - when they disagree, you have made an error somewhere and
should stop before compounding it.

In poor visibility, use attack points: navigate to a large, unmistakable
feature near your target, then make a short precise leg from it.
"""),

    ("Magnetic variation and back bearings", ["field", "navigation"], """
Three norths: True (the pole), Grid (the map's grid lines), Magnetic (where the
needle points). The difference between grid and magnetic is the one that
matters on the hill.

UK magnetic variation is small and changes over time - it passed through zero
in much of Britain during the 2010s and is now slightly EAST in most of the
country. Check the current figure in the map margin; a map older than a few
years will state a variation that is no longer correct.

Grid to Magnetic: ADD the variation (when variation is west) - remembered as
"Grid to Mag, Add" / "Mag to Grid, Get Rid". Reverse the sign for easterly
variation. With UK variation now near zero the correction is often negligible,
but the RULE still matters elsewhere.

Back bearing: add or subtract 180 degrees. Used to check you are on the line
you think you are - sight back at the feature you left.
"""),

    # ---------------------------------------------------------------- water
    ("Water purification: what each method kills", ["field", "water"], """
| Method            | Bacteria | Viruses | Protozoa (Crypto/Giardia) | Chemicals |
|-------------------|----------|---------|---------------------------|-----------|
| Boiling           | Yes      | Yes     | Yes                       | No        |
| Chlorine tablets  | Yes      | Yes     | Giardia yes, Crypto POOR  | No        |
| Chlorine dioxide  | Yes      | Yes     | Yes (needs longer for Crypto) | No    |
| Iodine            | Yes      | Yes     | Giardia yes, Crypto NO    | No        |
| 0.2 um filter     | Yes      | NO      | Yes                       | No        |
| UV pen            | Yes      | Yes     | Yes                       | No        |

Boiling: bring to a rolling boil. At altitude below about 2,000 m, one minute
at a rolling boil is sufficient; above that, three minutes. Time at temperature
matters more than duration of boil - water is already pasteurised well before
it boils.

Cryptosporidium is the awkward one: chlorine-resistant, so filtration or
boiling rather than tablets.

Filter first if the water is cloudy - turbidity defeats both UV and chemicals
by shielding organisms.
"""),

    ("Dehydration and hyponatraemia", ["field", "medical", "water"], """
Both come from getting fluid wrong, in opposite directions, and both present
with headache, nausea and confusion - which is why the amount you drink is
worth thinking about rather than guessing.

Dehydration: dark urine, thirst, headache, reduced output, tachycardia. In heat
with effort, fluid loss can exceed a litre an hour.

Hyponatraemia: too much plain water without salt, diluting blood sodium. Same
early symptoms, but urine is CLEAR and copious. Continuing to drink makes it
worse, and it can be fatal.

Rule of thumb for a hard day in heat: drink to thirst plus a little, take salt
with it - food, electrolyte tabs, salty snacks - and use urine colour as the
check. Pale straw is the target. Clear and frequent, with symptoms, is a
warning rather than a success.
"""),

    # --------------------------------------------------------------- ropes
    ("Knots worth actually knowing", ["field", "rope"], """
| Knot            | Use                                             |
|-----------------|-------------------------------------------------|
| Figure-of-eight on a bight | Fixed loop, easy to check, easy to untie after load |
| Bowline         | Fixed loop, ties fast, MUST be backed up        |
| Clove hitch     | Attach to a post, adjustable, slips under changing load |
| Round turn and two half hitches | Attach to a ring or bar under load  |
| Prusik          | Friction hitch that grips a rope under load, slides when unloaded |
| Alpine butterfly| Loop in the middle of a rope, loads in any direction |
| Tape knot       | Joining flat tape - the ONLY knot for tape      |
| Double fisherman| Joining two ropes, or closing a prusik loop     |

The figure-of-eight is preferred over the bowline where you cannot inspect it
later: it is visually obvious when tied wrong, and a bowline is not.

A knot reduces rope strength by 25 - 50 percent depending on the knot. That is
not a reason to avoid knots; it is a reason to know the working load, not the
breaking strain.
"""),

    ("River crossing: when not to, and how", ["field", "water", "emergency"], """
The first decision is whether to cross at all. Most river-crossing deaths are
of people who did not need to cross.

Do not cross if:
- Water is above mid-thigh on the shortest person
- It is moving fast enough that you cannot see the bottom
- The water is silty brown and rising - it is in spate
- There is a strainer, weir or drop downstream
- Someone in the party cannot swim, and there is any alternative

Choose the site, not the moment: widest point (shallowest, slowest), straight
section, firm bottom, safe exit on BOTH banks, and a clear runout below.

Technique: face upstream, angle downstream as you cross, shuffle rather than
step, keep two points of contact. Unclip the waist belt of a rucksack -
buoyancy is useful, being pinned by a pack is not.

Groups: link arms in a line parallel to the flow, strongest upstream. Never
rope a person to a fixed point in moving water.
"""),

    # -------------------------------------------------------------- shelter
    ("Emergency shelter priorities", ["field", "shelter"], """
Order matters, and it is not the order people assume.

1. INSULATION FROM THE GROUND. Conduction takes heat far faster than air.
   A rucksack, rope, foam mat, heather - anything between you and the ground
   is worth more than another layer on top.
2. WIND. Convective loss rises sharply with wind speed. Get behind something.
3. WET. Wet clothing conducts heat roughly 25 times faster than dry. Change
   or remove the wet layer if there is any dry alternative.
4. Then a roof.

A group shelter (bothy bag) works by trapping body heat and cutting wind. It
raises the internal temperature within minutes and is the single most effective
item of casualty kit for its weight and cost.

Sit ON your rucksack. Get everyone in together - a group of four in one shelter
is warmer than four alone.
"""),

    ("Wind chill and its actual effect", ["field", "weather"], """
Wind chill describes how fast exposed skin loses heat, not a lower air
temperature. Water at 5 C does not freeze because the wind blows.

What it does affect is exposed flesh and anyone wet. Rough guide at 5 C air:

| Wind speed | Feels like | Frostbite risk to exposed skin |
|------------|------------|--------------------------------|
| Calm       | 5 C        | None                           |
| 20 km/h    | 1 C        | Low                            |
| 50 km/h    | -2 C       | Low but rising                 |

At sub-zero air temperatures the same wind speeds become dangerous quickly.

The practical point: a forecast temperature is not the number to plan on.
Windchill plus wet is what causes hypothermia on British hills in summer, and
it does so at air temperatures people consider mild.
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
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:60]


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
        doc = frontmatter(title, tags, now) + f"# {title}\n" + body.rstrip() + "\n"
        path.write_text(doc, encoding="utf-8")
        written += 1
    print(f"  {written} written, {skipped} already present, {len(NOTES)} defined")
    print(f"  vault now: {len(list(VAULT.glob('*.md')))} notes")


if __name__ == "__main__":
    main()
