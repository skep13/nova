"""Emergencies, work, kitchen technique, computing, weather, damp.

The fourth batch. Where the earlier ones filled measured holes in specific
domains, this widens the base: the numbers to ring when something is actually
wrong, the employment rights people are talked out of, the cooking technique
that separates a good result from a grey one, and the household faults that
look alike and have completely different fixes.

Same rules as the rest. Written directly, dense enough to survive a
900-character excerpt, UK conventions, and nothing stated I am not confident
of. Emergency numbers are the one category where being wrong is unforgivable,
so those are the ones I have kept shortest and plainest.

    python3 build_practical_notes.py [vault-dir]
"""
import datetime
import pathlib
import re
import sys

VAULT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/orb/mem")

NOTES = [
    # ----------------------------------------------------------- emergencies
    ("UK emergency and urgent numbers", ["ref", "emergency", "uk"], """
| Number         | For                                            |
|----------------|------------------------------------------------|
| 999 or 112     | Police, fire, ambulance, coastguard, mountain rescue |
| 112            | Works on any network, including with no SIM    |
| 111            | NHS, urgent but not life-threatening (England, Wales, Scotland) |
| 101            | Police, non-emergency                           |
| 105            | Power cut - any supplier, anywhere in Britain   |
| 0800 111 999   | Gas emergency - smell of gas, 24 hours          |
| 0800 80 70 60  | Environmental incident hotline                  |
| 159            | Connects you securely to your own bank          |

Silent solution: if you call 999 and cannot speak, listen for the prompt and
press 55 on a mobile. Coughing or tapping is not enough - the system needs 55.

Ask for the service by name. Mountain rescue and cave rescue are requested
through the POLICE, not the ambulance service.

Register a vulnerable person on their energy supplier's Priority Services
Register before they need it, not during a cut.
"""),

    ("Gas smell, power cut, water leak: first actions", ["ref", "emergency", "home"], """
GAS - if you smell gas:
- Do NOT touch any electrical switch, including turning one off. A spark is a
  spark either way
- No naked flames, no doorbell, no mobile phone indoors
- Open doors and windows
- Turn the supply off at the meter if you can reach it safely
- Get out, then ring 0800 111 999 from outside

POWER CUT:
- Check whether neighbours are off too, and check your own trip switches
- Ring 105 - free, and routes to the right network operator
- Turn off appliances that were on, especially heaters and ovens, so they do
  not all restart at once
- A freezer keeps food safe for roughly 24 hours if the door stays SHUT

WATER LEAK:
- Find the internal stopcock and turn it clockwise. Usually under the kitchen
  sink, sometimes in a downstairs loo or under the stairs
- Know where it is BEFORE you need it, and turn it fully off and on once a year
  so it does not seize
- Turn off the electricity at the consumer unit if water is anywhere near it
"""),

    ("Fires: what to do and what not to", ["ref", "emergency", "home"], """
The default is always: get out, stay out, ring 999. Fighting a fire is the
exception, not the rule, and only when it is small, you have a clear exit
behind you, and you are not alone in the building.

CHIP PAN or any cooking oil fire:
- NEVER water. It flashes to steam and throws burning oil across the room
- Turn off the heat if you can reach it
- Smother - a fire blanket, or a damp (not dripping) cloth laid over
- Leave it alone for 30 minutes. Uncovering it early lets it reignite

ELECTRICAL: cut the power first if you safely can. CO2 or dry powder
extinguisher, never water while it is live.

FIRE BLANKET goes ON, laid over, not thrown.

Close doors behind you as you leave. A closed internal door buys a great deal
of time, and is the single most effective thing most people never do.

Test smoke alarms monthly. Replace the whole unit after ten years - the sensor
degrades whether or not the battery is fresh.
"""),

    ("Jump starting a car, in the right order", ["ref", "vehicles"], """
Order matters, and the last connection is the one people get wrong.

1. Both engines OFF, handbrakes on, cars not touching
2. RED to the FLAT battery's positive (+)
3. RED to the GOOD battery's positive (+)
4. BLACK to the GOOD battery's negative (-)
5. BLACK to an unpainted METAL earthing point on the flat car - a bolt or
   bracket away from the battery. NOT to the flat battery's negative terminal

Step 5 is the safety one. A charging battery vents hydrogen, and the final
connection is the one that sparks. Make that spark away from the gas.

Start the good car, run it a few minutes, then start the flat one. Once running,
remove in exact reverse order.

Then DRIVE it for 20-30 minutes. Idling barely charges anything.

If the battery goes flat again within a day or two, it is the battery or the
alternator, and jump starting is a diagnosis rather than a fix.

Do not jump start a visibly damaged, leaking or frozen battery.
"""),

    # ---------------------------------------------------------------- work
    ("Holiday, sick pay and notice: the statutory floor", ["ref", "work", "uk"], """
These are minimums. A contract can be more generous and cannot be less.

HOLIDAY: 5.6 weeks per year statutory. For a five-day week that is 28 days,
and an employer MAY include bank holidays within it. Part-timers get the same
5.6 weeks pro rata. It accrues from day one, including during a probation
period.

SICK PAY: Statutory Sick Pay is payable from the fourth consecutive day of
sickness, for up to 28 weeks, if you earn above the lower earnings limit. Many
employers pay more under a company scheme; the rate changes annually.

NOTICE:
| Service            | Employer must give | You must give |
|--------------------|--------------------|---------------|
| 1 month - 2 years  | 1 week             | 1 week        |
| 2 - 12 years       | 1 week per year    | 1 week        |
| 12 years or more   | 12 weeks           | 1 week        |

Two years' service is the usual threshold for ordinary unfair dismissal claims,
but there are exceptions with no qualifying period at all - discrimination,
whistleblowing, and asserting a statutory right among them.

ACAS is the free source for any of this, and their helpline is genuinely good.
"""),

    ("Payslips: what the deductions are", ["ref", "work", "money", "uk"], """
| Line             | What it is                                      |
|------------------|-------------------------------------------------|
| Gross pay        | Before anything is taken                        |
| Income tax (PAYE)| Tax on earnings above your personal allowance   |
| National Insurance| Separate from tax; builds State Pension entitlement |
| Pension          | Yours, plus employer's, plus tax relief         |
| Student loan     | A percentage above a threshold, by plan type    |
| Net pay          | What arrives                                    |

Your TAX CODE drives the tax figure. 1257L was the standard code for several
years; codes change, and a wrong one is the commonest cause of over- or
under-payment. BR means everything taxed at basic rate - correct for a second
job, wrong for a main one. A code ending W1 or M1 is emergency and non-
cumulative.

Check the code after: starting a job, ending one, getting a company benefit, or
any month the net pay changes without a reason you can name.

Overpaid tax is reclaimable, generally for four years back. HMRC does not always
notice on its own.
"""),

    # ------------------------------------------------------------- kitchen
    ("Resting meat, and why it matters", ["ref", "cooking"], """
Muscle fibres contract under heat and squeeze moisture toward the centre.
Resting lets them relax and the juices redistribute. Cut too early and it runs
onto the board instead of staying in the meat.

| Cut                | Rest for      |
|--------------------|---------------|
| Steak              | 5 minutes     |
| Chicken breast     | 5 minutes     |
| Whole chicken      | 15-20 minutes |
| Beef or lamb joint | 20-30 minutes |
| Large turkey       | 30-45 minutes |

Rest loosely covered with foil, not sealed - trapped steam softens any crust
you worked for.

Carryover cooking: a large joint keeps rising 2-5 C after it leaves the oven.
Pull it BELOW the target temperature and let it arrive there while resting.

A joint will stay hot far longer than people expect. Resting is almost never
the reason dinner was cold; being unready is.
"""),

    ("Salt: when to add it changes what it does", ["ref", "cooking"], """
Salt does different jobs at different times, and "season to taste at the end"
throws most of them away.

EARLY, on meat: salt dissolves, is drawn in, and denatures proteins so they
hold moisture. Effectively a dry brine. Either salt immediately before cooking,
or at least 40 minutes ahead - the window in between is the worst, because the
surface is wet and will not brown.

EARLY, in cooking water: pasta and vegetables absorb it. Water salted properly
seasons from within; salt added afterwards only sits on the outside.

DURING, in layers: seasoning each stage builds depth. A stew salted only at the
end tastes salty, not seasoned.

LATE, as finishing salt: flaky salt on top gives crunch and bursts of flavour
that dissolved salt cannot.

Salts differ hugely by volume - a teaspoon of fine table salt is far more
sodium than a teaspoon of flaky sea salt. Recipes usually mean fine unless they
say otherwise. Measure by weight if it matters.
"""),

    ("Substitutions that actually work", ["ref", "cooking"], """
| Missing              | Use instead                                   |
|----------------------|-----------------------------------------------|
| Buttermilk, 250 ml   | 250 ml milk + 1 tbsp lemon juice, stand 10 min |
| Self-raising, 100 g  | 100 g plain + 1 tsp baking powder             |
| Baking powder, 1 tsp | 1/4 tsp bicarb + 1/2 tsp cream of tartar      |
| 1 egg (binding)      | 1 tbsp ground flax + 3 tbsp water, stand 5 min |
| Caster sugar         | Granulated, blitzed briefly                   |
| Crème fraîche        | Soured cream, or Greek yoghurt (do not boil)  |
| Wine, for deglazing  | Stock plus a splash of vinegar                |
| Fresh herbs, 1 tbsp  | 1 tsp dried - dried is stronger, and goes in earlier |

What does NOT substitute: bicarbonate of soda for baking powder straight across
(bicarb needs an acid present), and butter for oil in pastry (the water content
in butter is doing structural work).

Dried herbs go in early to rehydrate and release; fresh go in late or they lose
everything. Rosemary, thyme and bay are the exceptions that take long cooking.
"""),

    ("Knives: sharpening, honing, and looking after them", ["ref", "cooking", "tools"], """
Honing and sharpening are different jobs. A steel does NOT sharpen - it
realigns an edge that has rolled over. Sharpening removes metal to create a new
edge.

- Hone: every few uses, on a steel or ceramic rod
- Sharpen: a few times a year, on a whetstone or with a pull-through as a last
  resort (pull-throughs remove a lot of metal and set a crude angle)

A blunt knife is more dangerous than a sharp one. It needs force, and force
slips.

Never: dishwasher (heat and detergent wreck both edge and handle), glass or
stone boards (they blunt instantly), leaving it in the sink, or twisting the
blade to prise anything.

Wash by hand, dry immediately - carbon steel rusts within minutes.

Wooden and plastic boards are both fine. Wood is kinder to the edge and is
naturally antibacterial; plastic goes in the dishwasher. Use separate boards
for raw meat.
"""),

    # ------------------------------------------------------------ computing
    ("Wi-Fi: channels, bands and why it drops", ["ref", "computing"], """
| Band   | Range      | Speed | Congestion             |
|--------|------------|-------|------------------------|
| 2.4 GHz| Best       | Lower | Worst - shared with everything |
| 5 GHz  | Moderate   | High  | Much less              |
| 6 GHz  | Shortest   | Highest | Almost none, needs Wi-Fi 6E |

On 2.4 GHz only channels 1, 6 and 11 do not overlap. Anything else overlaps two
neighbours and makes things worse for everyone. If you set a channel manually,
use one of those three.

2.4 GHz shares its band with microwaves, cordless phones, baby monitors and
Bluetooth. A microwave running is a genuine, measurable cause of dropouts.

Range beats speed for most problems: a weak 5 GHz signal is slower than a
strong 2.4 GHz one. Most devices choose badly and cling to the wrong one.

Placement matters more than hardware. Central, high, out in the open, away from
metal, mirrors, and water tanks. A router in a cupboard behind a boiler is
solving the wrong problem expensively.

Powerline adapters and mesh both beat a repeater, which halves throughput by
design.
"""),

    ("File sizes: what the units actually mean", ["ref", "computing"], """
| Unit | Bytes            | Roughly                        |
|------|------------------|--------------------------------|
| KB   | 1,000            | A page of plain text           |
| MB   | 1,000,000        | A photo, a minute of MP3       |
| GB   | 1,000,000,000    | A film, 250 photos             |
| TB   | 1,000,000,000,000| A large drive                  |

Two systems exist and they disagree. Manufacturers use decimal (1 GB = 10^9),
operating systems traditionally used binary (1 GiB = 2^30 = 1,073,741,824). A
"1 TB" drive shows as about 931 GB in Windows. Nothing has been lost - the two
are counting differently.

Bits versus bytes: 8 bits to a byte. Broadband is sold in megabits per second
(Mb/s), files are measured in megabytes (MB). A 100 Mb/s line downloads at
about 12.5 MB/s at best. That factor of eight is why "100 meg" feels slower
than expected.

Rough sizes: 3-minute MP3 3 MB, phone photo 3-5 MB, RAW photo 25 MB, hour of
1080p video 3 GB, hour of 4K 20 GB.
"""),

    ("Backups: the 3-2-1 rule and what counts", ["ref", "computing"], """
Three copies of anything you care about, on two different kinds of media, with
one of them off-site.

The rule exists because the common failure modes are correlated. A fire, a
theft, a flood or a ransomware encryption takes everything in one building at
once, and RAID is not a backup - it protects against a disk dying, not against
deleting the wrong folder.

What does NOT count as a backup:
- A second folder on the same drive
- RAID or a mirrored pair
- A sync service on its own - sync propagates deletion, which is the point of
  sync and the enemy of backup. Versioning helps, if it goes back far enough

Test a RESTORE, not the backup. An untested backup is a belief, not a
protection, and the moment you find out is the worst possible moment.

For a home setup: an external drive that is not permanently connected, plus
something off-site or in the cloud. Unplugged matters - ransomware encrypts
whatever it can reach.
"""),

    # -------------------------------------------------------------- weather
    ("Beaufort scale, and what the wind is doing", ["ref", "weather"], """
| Force | mph   | Name            | What you see                        |
|-------|-------|-----------------|-------------------------------------|
| 0     | <1    | Calm            | Smoke rises vertically              |
| 2     | 4-7   | Light breeze    | Leaves rustle, wind felt on face    |
| 4     | 13-18 | Moderate        | Dust and loose paper raised         |
| 5     | 19-24 | Fresh           | Small trees sway                    |
| 6     | 25-31 | Strong          | Large branches move, umbrellas fail |
| 7     | 32-38 | Near gale       | Whole trees move, hard to walk      |
| 8     | 39-46 | Gale            | Twigs break off trees               |
| 9     | 47-54 | Severe gale     | Slates and chimney pots come off    |
| 10    | 55-63 | Storm           | Trees uprooted, structural damage   |

Gusts run roughly 1.5 times the mean wind speed, and it is the gust that takes
a fence down or a person off their feet.

Above force 6 outdoor work on a ladder is a bad idea; above force 7 walking
exposed ground is genuinely difficult.

Met Office warnings: yellow means be aware, amber means be prepared and expect
disruption, red means take action and there is a danger to life.
"""),

    # ---------------------------------------------------------------- damp
    ("Damp: three kinds that look alike", ["ref", "home"], """
Nearly all household damp is CONDENSATION, and nearly all of it is treated as
though it were something else and more expensive.

| Type       | Where it appears                    | Cause                  |
|------------|-------------------------------------|------------------------|
| Condensation | Cold surfaces, corners, behind furniture, window reveals. Black spotty mould | Moist air meeting cold surfaces |
| Penetrating | A patch that worsens after rain, at any height | Water getting in - gutter, pointing, roof, sill |
| Rising     | Low down only, a tide mark under about a metre, often with salts | Ground moisture up through the wall |

Rising damp is far rarer than the number of firms selling treatment for it.

Condensation is fixed by the three together: produce less moisture (lids on
pans, vent the tumble dryer, dry washing outside), remove what you produce
(extractor fans that actually run, trickle vents open), and keep surfaces
warmer (background heat, insulation, furniture off cold external walls).

Mould on the cold side of a cold external wall behind a wardrobe is the
signature. Move the wardrobe five centimetres out and much of it stops.
"""),

    ("Frozen and burst pipes", ["ref", "home", "emergency"], """
PREVENTION: lag pipes in lofts, garages and against external walls. Keep some
background heat when away in a cold snap - a house allowed to drop to freezing
costs far more than the heating you saved. Know where the stopcock is.

IF A PIPE FREEZES:
- Turn off the stopcock
- Open the nearest tap so meltwater has somewhere to go
- Thaw gently, from the tap END back toward the frozen section - hot water
  bottle, towels soaked in warm water, hairdryer on low
- NEVER a blowtorch or naked flame

IF A PIPE BURSTS:
- Stopcock off immediately
- Electricity off at the consumer unit if water is near any of it
- Open all cold taps to drain the system down
- Catch what you can, and photograph the damage before clearing up - insurers
  ask

The damage is rarely from the freeze itself. Ice expands, splits the pipe, and
nothing happens until it THAWS - which is when an unattended house floods.
"""),

    # ---------------------------------------------------------------- body
    ("Screens: eyes, posture and RSI", ["ref", "wellbeing"], """
20-20-20: every 20 minutes, look at something 20 feet away for 20 seconds. Eye
strain comes from sustained focus at one distance, not from the screen itself.
Blink rate drops by more than half when concentrating, which is why eyes feel
dry.

Position: top of the screen at or just below eye level, an arm's length away.
Looking slightly DOWN is correct; looking up strains neck and eyes both.

Chair: feet flat, knees roughly level with hips, lower back supported.
Elbows about 90 degrees, wrists straight and floating - not resting on the
desk edge while typing.

RSI warning signs: ache that persists after stopping, tingling, weakness,
night pain. These are worth acting on early - it is far easier to prevent than
to treat, and people routinely work through the early stage.

The best posture is the next one. Fixed position is the problem, however
correct; get up every half hour or so.
"""),

    ("Caffeine: dose, timing and half-life", ["ref", "wellbeing"], """
Half-life around 5 hours in a typical adult, meaning half is still circulating
five hours later and a quarter after ten. A 4 pm coffee is still measurably
present at midnight.

| Source              | Caffeine   |
|---------------------|------------|
| Filter coffee, mug  | 100-140 mg |
| Espresso, single    | 60-80 mg   |
| Instant, mug        | 60-80 mg   |
| Tea, mug            | 40-70 mg   |
| Green tea           | 30-50 mg   |
| Cola, 330 ml        | 30-40 mg   |
| Energy drink, 250 ml| 80 mg      |

Guidance for most healthy adults is up to about 400 mg a day; 200 mg in
pregnancy. Sensitivity varies enormously and is partly genetic.

It does not create energy. It blocks adenosine, the molecule that signals
tiredness - the tiredness is still accumulating underneath, which is why the
crash arrives when it clears.

Tolerance builds within days. Withdrawal headaches are real and peak around 24
to 48 hours; taper rather than stopping dead.
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
