"""
Combinatorial filler: the material that carries a transcript to an arbitrary
token target without visible repetition.

A hand-written corpus cannot do this.  One million tokens is about four million
characters; a few dozen curated paragraphs would have to repeat hundreds of
times.  So the filler is generated from slot templates instead, and the slot
product is what supplies the variety: ~60 sentence shapes over vocabularies of
people, teams, projects, artifacts, customers, metrics, dates, numbers and
ticket ids give a combinatorial space far larger than any transcript needs.

Two invariants keep this safe for grading:

  * filler NEVER mentions a governed entity, so it can never be mistaken for a
    rule and can never change the closure;
  * filler NEVER uses the rule register (approve / prohibit / supersede /
    reaffirm), so it does not even look like policy.

The curated, rule-bearing prose -- decisions, and the near-miss chatter that is
meant to look like policy -- stays small and hand-written, because that is
where precision matters.  This module only supplies volume.
"""
from __future__ import annotations

import random
from typing import Dict, List, Sequence

FIRST = ("Ana Ben Cira Dov Esme Faye Gus Hana Ines Jonas Kira Lars Mira Nils Oona Piet "
         "Rhea Sami Tova Umar Vera Wes Yara Zane Ada Bo Cato Dilan Eve Foss Gita Hugo "
         "Iva Jarl Kaya Leif Mai Noor Orla Pim Quill Rune Sena Tam Ubah Vidar Wren Xiu "
         "Yusra Zeph").split()
LAST = ("Aldridge Barrow Calder Dunhill Ewart Falk Grieve Halloran Ives Jarrold Kessler "
        "Lund Merrick Nyholm Ostrom Pike Quennell Rowntree Sandell Thirlwall Udall Vance "
        "Wexford Yardley Zubrin Ashby Braid Corrin Delahaye Ennis").split()
# teams are split by what they plausibly do, so a template can ask for the
# right kind rather than drawing "legal is hiring more engineers"
ENG_TEAMS = ("platform, data, mobile, infra, security, QA, research, "
             "search, payments-eng, integrations").split(", ")
BIZ_TEAMS = ("growth, support, billing, partnerships, revops, people ops, finance, "
             "legal, marketing, solutions, docs, design, localisation").split(", ")
TEAMS = ENG_TEAMS + BIZ_TEAMS
PROJECTS = ("Harbour, Quill, Ledger, Beacon, Willow, Tessellate, Halyard, Kingfisher, "
            "Lantern, Meridian, Nightjar, Orchard, Pennant, Quarry, Rookery, Saltmarsh, "
            "Thicket, Undertow, Vellum, Waypoint, Yarrow, Zephyr, Bramble, Coppice, "
            "Dovetail, Elmwood, Fathom, Gantry, Hollow, Inlet").split(", ")
ARTIFACTS = ("the onboarding flow, the export pipeline, the retention dashboard, "
             "the pricing page, the audit log viewer, the bulk importer, the alerting rules, "
             "the seat-management screen, the SSO setup guide, the trial banner, "
             "the usage report, the webhook retry logic, the search ranking, "
             "the mobile navigation, the invoice PDF, the sandbox reset job, "
             "the changelog feed, the permissions matrix, the CSV template, "
             "the status page, the deprecation notices, the migration runbook, "
             "the load test harness, the schema registry, the feature-flag console").split(", ")
CUSTOMERS = ("Brightmoor, Calderwood, Denholm, Eastvale, Fernbrook, Greystone, Hartfield, "
             "Ironside, Jessup, Kelmscott, Larchmont, Marlowe Group, Northbay, Oakridge, "
             "Pemberton, Quarrymill, Redhaven, Stonebridge, Thornbury, Umberfield, "
             "Vinehall, Westcliff, Yewtree, Zandvoort").split(", ")
METRICS = ("p95 latency, activation rate, weekly active seats, ticket backlog, "
           "trial-to-paid conversion, churn, error budget burn, index freshness, "
           "queue depth, first-response time, crash-free sessions, NPS, "
           "onboarding completion, export volume, seat utilisation").split(", ")
CITIES = ("Leeds, Utrecht, Porto, Tallinn, Malmo, Cork, Graz, Ghent, Bergen, Kaunas, "
          "Brno, Rennes, Aarhus, Bilbao, Trieste").split(", ")
VERBS = ("draft, circulate, review, scope, spike, benchmark, document, unblock, triage, "
         "retire, backfill, rehearse, chase, consolidate, annotate, timebox, "
         "re-baseline, socialise, dry-run, sanity-check").split(", ")
MONTHS = ("January February March April May June July August September October "
          "November December").split()

# Sentence shapes.  Slots are typed, so numbers land in plausible ranges and a
# template can ask for an engineering team where only an engineering team makes
# sense.  {p} person, {te} engineering team, {tb} business team, {t} any team,
# {j} project, {a} artifact, {u} customer, {m} metric, {city}, {mon} month,
# {d} date, {tk} ticket, {v} verb, and the numeric slots named below.
STATUS = [
    "{p} took the room through {j}: {n_few} of {n_few2} workstreams are green, the rest slip to {d}.",
    "{j} is at {pct} of the milestone; {te} flagged {a} as the long pole.",
    "{te} closed {n_tickets} tickets on {j} this week and opened {n_tickets2}.",
    "Progress on {j} was reviewed. {p} noted that {a} still has no owner.",
    "{p}: {j} is unblocked as of {d}, testing starts with {te}.",
    "{te} demoed {a}. Feedback was mostly about copy, {p} to collect it in {tk}.",
    "{j} slipped a week. {p} put the cause down to review latency, not scope.",
    "Two of {te}'s three {j} spikes came back inconclusive; {p} will rerun one.",
    "{p} reported {j} is now behind {a} in priority order.",
    "{te} has {n_few} people on {j} until {d}, then drops to {n_small}.",
    "{j} is code complete. {te} wants {n_weeks} weeks of soak before enabling it.",
    "{p} showed the {j} burndown; {n_pct_small} of the scope was added after kickoff.",
]
METRIC = [
    "{m} improved by {pct} over the last {n_weeks} weeks. {p} attributes it to {a}.",
    "{m} is flat. {tb} wants another {n_weeks} weeks before drawing a conclusion.",
    "{p} showed {m} broken down by plan: {pct} of the change sits in one cohort.",
    "{m} regressed after the {j} rollout. {tk} tracks the investigation.",
    "{m} was the best it has been this {mon}, up {n_pct_small} on the quarter.",
    "{te} disputed the {m} definition. {p} to write it down in {a}.",
    "Two dashboards disagree on {m} by about {n_pct_small}. {p} owns reconciling them.",
    "{m} for {u} is well outside the band {te} expected; {p} is digging in.",
    "{p} noted {m} has moved {pct} since the {j} launch, in the wrong direction.",
]
ESCALATION = [
    "{u} escalated over {a}. {p} is on it with {tb}; a written update goes out {d}.",
    "{u} asked for {a} again. {p} said the answer is still not this quarter.",
    "{tb} handled {n_small} P2s from {u} this week, all traced back to {a}.",
    "{p} relayed that {u} is unhappy with response times on {tk}.",
    "{u}'s renewal is {mon}. {tb} listed {a} as the main risk.",
    "{p} and {tb} met {u} in {city}; the notes are attached to {tk}.",
    "{u} has asked for a written timeline on {a} by {d}.",
    "{p} flagged that two of {u}'s admins have raised {tk} separately.",
]
PEOPLE_OPS = [
    "{te} is hiring {n_small} more engineers; first interviews from {d}.",
    "{tb} has {n_small} open roles; {p} is chasing the agency shortlist.",
    "{p} starts on {t} on {d} and will pair with {t} for the first fortnight.",
    "{p} is out from {d}; {te} covers on-call.",
    "The {city} office moves floors in {mon}. {n_desks} desks, no change to the meeting rooms.",
    "{p} finished the {j} handover to {t}.",
    "Two people from {t} are speaking at a conference in {city} in {mon}.",
    "{p} raised that {t} has had {n_small} interview loops with no offer.",
    "Performance review calibration for {t} lands on {d}.",
    "{p} asked whether the {city} team keeps its {mon} team day. Undecided.",
]
OPS = [
    "There was a {n_min}-minute degradation on {d}; {te} wrote it up in {tk}.",
    "{p} walked through the {j} post-mortem. {n_small} action items, none blocking.",
    "The on-call rota for {mon} is published; {te} swaps with {te}.",
    "{te} is retiring {a} in {mon} after {n_weeks} weeks of deprecation notices.",
    "A dependency bump broke {a} in staging. {p} rolled it back within {n_min} minutes.",
    "{te} raised the cost of {a}: {n_pct_small} over plan for {mon}.",
    "Backups for {j} were restored as a drill on {d}. Restore took {n_min} minutes.",
    "{p} asked for {n_small} more days on the {j} freeze; {te} agreed.",
    "Alert volume for {j} is down; {te} tuned {n_small} rules on {d}.",
    "{te} finished the {a} migration over the weekend with {n_min} minutes of downtime.",
]
PLANNING = [
    "{p} opened the {mon} planning discussion. {t} wants {j} above {j}.",
    "{te} and {tb} disagreed on sequencing {j}; {p} will arbitrate offline.",
    "The roadmap draft has {n_few2} items for {mon}; {p} thinks {n_few} is realistic.",
    "{p} argued {a} should be a quarter goal, not a project. No conclusion reached.",
    "Budget for {j} is {n_k}k. {tb} asked whether {a} comes out of the same line.",
    "{te} presented three options for {a}. The room leaned towards the middle one.",
    "{p} noted the {mon} offsite conflicts with the {j} launch window.",
    "{j} was deferred to {mon}; {p} will tell the {u} account team.",
]
SIDE = [
    "{p} joined {n_min_small} minutes late; the recording covers the first item.",
    "Room booking moved to the {ord_floor} floor for the rest of {mon}.",
    "{p} apologised for the audio; the {city} office has building work on.",
    "Coffee machine on {n_floor} is fixed.",
    "{p} will not make next week's session and sends notes in advance.",
    "{t} asked to shorten this meeting to {n_meeting} minutes from {mon}.",
    "Someone's dog appeared on camera. Noted for the record with approval.",
    "{p} reminded everyone the survey closes {d}.",
    "The meeting overran by {n_min_small} minutes.",
    "{p} lost connection twice; {p} took over the notes.",
    "No apologies received this week.",
    "{p} asked for the slides to be circulated before the meeting next time.",
]
ACTIONS = [
    "{p} to {v} {a} by {d}.",
    "{p} to {v} the {j} plan with {t} before {d}.",
    "{t} to {v} {a} and report back on {d}.",
    "{p} to {v} {tk} and close it if {m} holds.",
    "{p} and {p} to {v} the {u} follow-up by {d}.",
    "{p} to {v} the {mon} figures for {m} and send them round.",
]

FAMILIES = {"status": STATUS, "metric": METRIC, "escalation": ESCALATION,
            "people": PEOPLE_OPS, "ops": OPS, "planning": PLANNING}


class Padder:
    """Draws filler lines that are unique by construction."""

    def __init__(self, rng: random.Random, banned: Sequence[str] = ()):
        self.rng = rng
        # never emit a line containing a governed entity name
        self.banned = [b.lower() for b in banned]
        self.people = [f"{f} {l}" for f in FIRST for l in LAST]
        rng.shuffle(self.people)
        # rejection-sample against what has already been emitted.  The slot
        # product is ~10^9 and a transcript needs ~10^4 lines, so a handful of
        # retries is enough to keep the visible repetition rate near zero.
        self.seen: set = set()

    def _slots(self) -> Dict[str, str]:
        r = self.rng
        return {
            "p": r.choice(self.people), "t": r.choice(TEAMS),
            "te": r.choice(ENG_TEAMS), "tb": r.choice(BIZ_TEAMS),
            "j": r.choice(PROJECTS), "a": r.choice(ARTIFACTS), "u": r.choice(CUSTOMERS),
            "m": r.choice(METRICS), "city": r.choice(CITIES), "v": r.choice(VERBS),
            "mon": r.choice(MONTHS), "d": f"{r.choice(MONTHS)[:3]} {r.randint(1, 28)}",
            "n_small": str(r.randint(2, 9)), "n_few": str(r.randint(2, 6)),
            "n_few2": str(r.randint(4, 12)), "n_weeks": str(r.randint(2, 8)),
            "n_min": str(r.randint(4, 55)), "n_min_small": str(r.randint(3, 12)),
            "n_meeting": str(r.choice((15, 20, 25, 30, 45))),
            "n_tickets": str(r.randint(6, 70)), "n_tickets2": str(r.randint(6, 70)),
            "n_desks": str(r.choice((24, 30, 36, 42, 48, 60, 72, 90))),
            "n_floor": str(r.randint(1, 6)),
            "ord_floor": r.choice(("first", "second", "third", "fourth", "fifth", "sixth")), "n_k": str(r.choice((15, 20, 30, 45, 60, 80, 120, 200))),
            "pct": f"{r.randint(4, 40)}%", "n_pct_small": f"{r.randint(3, 18)} percent",
            "tk": f"{r.choice(('HAL', 'PLT', 'OPS', 'SUP'))}-{r.randint(100, 9999)}",
        }

    def _draw(self, pool: Sequence[str], tries: int = 14) -> str:
        s = ""
        for _ in range(tries):
            s = self.rng.choice(pool).format(**self._slots())
            if s in self.seen or any(b in s.lower() for b in self.banned):
                continue
            self.seen.add(s)
            return s
        return s

    def line(self, family: str = "") -> str:
        return self._draw(FAMILIES[family] if family else
                          self.rng.choice(list(FAMILIES.values())))

    def side(self) -> str:
        return self._draw(SIDE)

    def action(self) -> str:
        return self._draw(ACTIONS)

    def block(self, lines: int = 0) -> List[str]:
        """A few lines on one subject.  Family is redrawn per line: taking every
        line of a block from one family exhausts that family's ten templates and
        is where visible repetition comes from."""
        fams = list(FAMILIES)
        main = self.rng.choice(fams)
        out = []
        for i in range(lines or self.rng.randint(2, 5)):
            out.append(self.line(main if i == 0 or self.rng.random() < 0.5
                                 else self.rng.choice(fams)))
        return out

    def capacity(self) -> int:
        """Rough count of distinct lines the slot product can produce."""
        n_tpl = sum(len(v) for v in FAMILIES.values())
        return n_tpl * len(self.people) * len(TEAMS) * len(PROJECTS) * len(ARTIFACTS)
