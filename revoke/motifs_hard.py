"""
Hard-tier motifs: long state arcs, speaker hierarchy, aliasing, dynamic groups,
context flip-flops and near-miss noise.

Every motif still speaks only the engine's language (allow/1, contexts, grp/2,
priorities), so grading is unchanged.  What changes is how much a system has to
keep straight at once, and how many statements *look* like rules without being
rules.

Priority arithmetic in this tier: pi = 10000 * rank + band + local, where rank
is the speaker's rank in the domain hierarchy.  A higher-ranked ruling therefore
beats a lower-ranked one regardless of order, which is exactly what the
hierarchy declaration at session 1 tells the agent.
"""
from __future__ import annotations

import random
from typing import Dict, List, Sequence, Tuple

from .events import Event
from .logic import Lit, Rule, lit
from .motifs import Beat, MotifPlan, Probe, _Ctx, _allow, _deny
from .domains.hard_ext import HARD, NOISE_KINDS, TERSE

# --------------------------------------------------------------------------
# hard-tier prose, per domain
# --------------------------------------------------------------------------

HNL: Dict[str, Dict[str, List[str]]] = {
 "devops": {
  "ALIAS": ["{x} follows {y}: whatever ruling applies to {y} applies to {x} as well, and this linkage overrides any separate ruling that names only {x}."],
  "ALIAS_BREAK": ["{x} no longer inherits blocks from {y}; from now on only rulings that name {x} directly restrict it."],
  "GROUP_BAN_COND": ["Nothing in {g} may be called while {c}. ({g} currently: {roster}.)"],
  "JOIN": ["{e} has been added to {g}.", "{e} now belongs to {g}."],
  "LEAVE": ["{e} has been removed from {g}.", "{e} is no longer part of {g}."],
  "LIFT": ["The block on {e} is lifted. We have no further ruling on {e}; whatever the pipeline owners decide applies.",
           "We are withdrawing our block on {e}. No position on it from our side beyond that."],
  "REVERSE": ["The retirement of {e} is reversed -- {e} is callable again.",
              "Reinstating {e}: the earlier decommissioning is undone."],
  "LEAD_DEFAULT": ["We are making {e} our default for this pipeline.", "{e} is the standard here going forward."],
  "SEC_BAN": ["{e} is blocked. This is a policy ruling.", "Policy: {e} may not be called."],
 },
 "procurement": {
  "ALIAS": ["{x} is handled as an affiliate of {y}: any ruling on {y} applies equally to {x}, and this linkage overrides any separate decision that names only {x}."],
  "ALIAS_BREAK": ["{x} is no longer treated as an affiliate of {y}; only decisions naming {x} directly restrict it now."],
  "GROUP_BAN_COND": ["Nothing from {g} may be purchased while {c}. ({g} currently: {roster}.)"],
  "JOIN": ["{e} has been moved into {g}.", "{e} is now classified under {g}."],
  "LEAVE": ["{e} has been taken out of {g}.", "{e} no longer sits in {g}."],
  "LIFT": ["The bar on {e} is lifted. We take no further position on {e}; sourcing decisions on it are the lead's.",
           "We are withdrawing our bar on {e}, with no ruling either way beyond that."],
  "REVERSE": ["The decision to drop {e} is reversed -- {e} is approved again.",
              "Reinstating {e}: the earlier removal is undone."],
  "LEAD_DEFAULT": ["We are making {e} our default supplier for this line.", "{e} is the preferred source here from now on."],
  "SEC_BAN": ["{e} is barred. This is a compliance ruling.", "Ruling: no purchase orders to {e}."],
 },
 "clinical": {
  "ALIAS": ["{x} is to be treated exactly like {y} for this patient: any order or hold on {y} applies to {x} as well, and this linkage overrides any separate note that names only {x}."],
  "ALIAS_BREAK": ["{x} is no longer tied to {y}; only orders naming {x} directly restrict it from here."],
  "GROUP_BAN_COND": ["Nothing from {g} is to be given while {c}. ({g} currently: {roster}.)"],
  "JOIN": ["{e} has been added to {g}.", "{e} is now classed under {g}."],
  "LEAVE": ["{e} has been taken out of {g}.", "{e} is no longer counted in {g}."],
  "LIFT": ["The hold on {e} is lifted. We have no further order on {e}; the resident's plan governs it.",
           "Withdrawing our hold on {e}. No position on it beyond that."],
  "REVERSE": ["The stop on {e} is reversed -- {e} is back on the plan.",
              "Reinstating {e}: the earlier discontinuation is undone."],
  "LEAD_DEFAULT": ["We are making {e} the standing choice for this patient.", "{e} is the regimen default going forward."],
  "SEC_BAN": ["{e} is contraindicated. This is a committee ruling.", "Ruling: {e} is not to be given."],
 },
 "smarthome": {
  "ALIAS": ["{x} follows {y}: any rule on {y} applies to {x} too, and that linkage wins over anything said only about {x}."],
  "ALIAS_BREAK": ["{x} no longer follows {y}; only rules that name {x} directly apply to it now."],
  "GROUP_BAN_COND": ["Nothing in {g} runs while {c}. ({g} currently: {roster}.)"],
  "JOIN": ["{e} has been added to {g}.", "{e} now counts as one of {g}."],
  "LEAVE": ["{e} has been taken out of {g}.", "{e} no longer counts as one of {g}."],
  "LIFT": ["The rule against {e} is lifted. No further position on it from here; whatever Sam decides applies.",
           "We are dropping our rule on {e}, nothing else implied."],
  "REVERSE": ["Changing that back -- {e} is allowed again.",
              "Reinstating {e}: the earlier ban is undone."],
  "LEAD_DEFAULT": ["Let's make {e} our evening default.", "{e} is the default from now on."],
  "SEC_BAN": ["{e} is not allowed. That is a charter rule.", "Rule: {e} stays off."],
 },
 "finance": {
  "ALIAS": ["{x} is controlled as a variant of {y}: any control on {y} applies to {x} as well, and this linkage overrides any separate delegation that names only {x}."],
  "ALIAS_BREAK": ["{x} is decoupled from {y}; only controls naming {x} directly restrict it from now on."],
  "GROUP_BAN_COND": ["Nothing in {g} may be executed while {c}. ({g} currently: {roster}.)"],
  "JOIN": ["{e} has been reclassified into {g}.", "{e} now falls under {g}."],
  "LEAVE": ["{e} has been reclassified out of {g}.", "{e} no longer falls under {g}."],
  "LIFT": ["The control on {e} is lifted. We take no further position on {e}; the desk head's delegation governs it.",
           "Withdrawing our control on {e}, with no ruling either way beyond that."],
  "REVERSE": ["The prohibition on {e} is reversed -- {e} is permitted again.",
              "Reinstating {e}: the earlier revocation is undone."],
  "LEAD_DEFAULT": ["We are making {e} the standard path for this desk.", "{e} is the default route going forward."],
  "SEC_BAN": ["{e} is not permitted. This is a control ruling.", "Ruling: {e} may not be executed."],
 },
}


class _HCtx(_Ctx):
    """Hard-tier context: merged entity names, speakers by rank, noise."""

    def __init__(self, idx: int, dom, rng: random.Random, names: Dict[str, str]):
        super().__init__(idx, dom, rng)
        self.names = names
        self.h = HARD[dom.key]

    def name(self, e: str) -> str:
        return self.names[e]

    def say(self, key: str, **kw) -> str:
        # ~40% of ordinary rule statements use a terse chat-like phrasing
        pool = list(self.dom.nl[key])
        if key in TERSE.get(self.dom.key, {}) and self.rng.random() < 0.4:
            pool = TERSE[self.dom.key][key]
        return self.rng.choice(pool).format(**kw)

    def hsay(self, key: str, **kw) -> str:
        return self.rng.choice(HNL[self.dom.key][key]).format(**kw)

    def who(self, rank: int) -> str:
        return self.rng.choice(self.h["speakers"][rank])

    def pr(self, k: int, rank: int = 1) -> int:
        return 10000 * rank + self.band + k

    def noise(self, kind: str, e: str) -> Tuple[str, str]:
        return (self.who(0), self.rng.choice(self.h["noise"][kind]).format(e=self.name(e)))


def _hev(c: _HCtx, kind: str, tag: str, text: str, rank: int = 1, **kw) -> Event:
    tags = tuple(kw.pop("tags", ())) + (f"rank:{rank}",)
    return Event(eid=c.eid(tag), kind=kind, text=text, motif=c.ns,
                 speaker=c.who(rank), tags=tags, **kw)


def _ctx_on(c: _HCtx, k: str, rank: int = 1) -> Event:
    return _hev(c, "ADD", f"ctx_{k}", c.say("CTX_ON", c=c.clause(k)), rank,
                rid=c.rid(f"k_{k}"), head=lit(k), prio=c.pr(1, rank), tags=("context",))


def _ctx_off(c: _HCtx, k: str, rank: int = 1) -> Event:
    return _hev(c, "SUPERSEDE", f"ctxoff_{k}", c.say("CTX_OFF", c=c.clause(k)), rank,
                rid=c.rid(f"k_{k}"), head=lit(f"~{k}"), prio=c.pr(1, rank), tags=("context",))


def _allow_ev(c: _HCtx, e: str, tag: str, k: int = 1, rank: int = 1, key: str = "ADD") -> Event:
    text = c.say(key, e=c.name(e)) if key in c.dom.nl else c.hsay(key, e=c.name(e))
    return _hev(c, "ADD", tag, text, rank, rid=c.rid(f"r_{e}"), head=_allow(c.dom, e), prio=c.pr(k, rank))


# --------------------------------------------------------------------------
# H1  context flip-flop
# --------------------------------------------------------------------------

def h_ctx_flipflop(c: _HCtx, ents, ctxs, grp) -> MotifPlan:
    d, x, alt, z = c.dom, ents[0], ents[1], ents[2]
    k = ctxs[0]
    b0 = Beat("open", [_allow_ev(c, x, "allow_x"), _allow_ev(c, alt, "allow_alt")],
              Probe("", (x, alt), "ADD", c.ns, "baseline"))
    b1 = Beat("condban", [
        _hev(c, "CONFLICT", "ban_x", c.say("CONFLICT", e=c.name(x), c=c.clause(k)),
             rid=c.rid("rbx"), head=_deny(d, x), body=(lit(k),), prio=c.pr(3)),
        _ctx_on(c, k),
    ], Probe("", (x, alt), "CONDITION", c.ns, "condition true: x banned"))
    b2 = Beat("clear", [
        _ctx_off(c, k),
        _hev(c, "CONFLICT", "ban_alt", c.say("ADD_BAN", e=c.name(alt)),
             rid=c.rid("rbalt"), head=_deny(d, alt), prio=c.pr(3)),
    ], Probe("", (x, alt), "CONDITION", c.ns, "condition false: x is the only licensed option"))
    b3 = Beat("retrigger", [_ctx_on(c, k), _allow_ev(c, z, "allow_z")],
              Probe("", (x, alt, z), "CONDITION", c.ns, "condition true again: x banned, z carries the task"))
    b4 = Beat("clear2", [_ctx_off(c, k)],
              Probe("", (x, alt, z), "CONDITION", c.ns, "x and z licensed, alt banned"))
    b5 = Beat("widen", [
        _hev(c, "CONDITION", "widen", c.say("CONDITION_WIDEN", e=c.name(x)),
             rid=c.rid("rbx"), body=(), prio=c.pr(3)),
    ], Probe("", (x, alt, z), "CONDITION", c.ns, "ban made unconditional: x banned for good"))
    return MotifPlan("ctx_flipflop", [b0, b1, b2, b3, b4, b5], [], (x, alt, z))


# --------------------------------------------------------------------------
# H2  alias: x inherits y's status
# --------------------------------------------------------------------------

def h_alias(c: _HCtx, ents, ctxs, grp) -> MotifPlan:
    d, x, y, alt = c.dom, ents[0], ents[1], ents[2]
    b0 = Beat("open", [_allow_ev(c, y, "allow_y"), _allow_ev(c, x, "allow_x"), _allow_ev(c, alt, "allow_alt")],
              Probe("", (x, y, alt), "ADD", c.ns, "baseline"))
    b1 = Beat("link", [
        _hev(c, "ADD", "alias_pos", c.hsay("ALIAS", x=c.name(x), y=c.name(y)), 2,
             rid=c.rid("ra_pos"), head=_allow(d, x), body=(_allow(d, y),), prio=c.pr(5, 2), tags=("override",)),
        _hev(c, "ADD", "alias_neg", "", 2,
             rid=c.rid("ra_neg"), head=_deny(d, x), body=(_deny(d, y),), prio=c.pr(5, 2), tags=("override", "silent")),
    ], Probe("", (x, y, alt), "ADD", c.ns, "linkage declared, nothing changes yet"))
    b2 = Beat("ban_y", [
        _hev(c, "CONFLICT", "ban_y", c.say("ADD_BAN", e=c.name(y)),
             rid=c.rid("rby"), head=_deny(d, y), prio=c.pr(3)),
    ], Probe("", (x, y, alt), "CONFLICT", c.ns, "y banned, x banned transitively"))
    b3 = Beat("restore_y", [
        _hev(c, "SUPPORT", "support_y", c.say("SUPPORT", e=c.name(y)), 2,
             rid=c.rid(f"r_{y}"), delta=6, tags=("override",)),
    ], Probe("", (x, y, alt), "SUPPORT", c.ns, "y reinstated, x follows"))
    b4 = Beat("unlink", [
        _hev(c, "RETRACT", "alias_break", c.hsay("ALIAS_BREAK", x=c.name(x), y=c.name(y)), 2,
             rid=c.rid("ra_neg"), instances=((x,),)),
        _hev(c, "CONFLICT", "ban_y2", c.say("SUPERSEDE", e=c.name(y)), 2,
             rid=c.rid("rby2"), head=_deny(d, y), prio=c.pr(9, 2)),
    ], Probe("", (x, y, alt), "RETRACT", c.ns, "y banned again but x no longer inherits it"))
    return MotifPlan("alias", [b0, b1, b2, b3, b4], [], (x, y, alt))


# --------------------------------------------------------------------------
# H3  dynamic group membership under a conditional blanket ban
# --------------------------------------------------------------------------

def h_group_dynamics(c: _HCtx, ents, ctxs, grp) -> MotifPlan:
    d, a, b, cc, alt = c.dom, ents[0], ents[1], ents[2], ents[3]
    k = ctxs[0]
    facts = [Rule(c.rid(f"g_{e}"), Lit("grp", (e, grp)), (), 1, session=0) for e in (a, b)]
    roster = f"{c.name(a)}, {c.name(b)}"
    b0 = Beat("open", [_allow_ev(c, e, f"allow_{e}") for e in (a, b, cc, alt)],
              Probe("", (a, cc, alt), "ADD", c.ns, "baseline"))
    b1 = Beat("groupban", [
        _hev(c, "CONFLICT", "grpban", c.hsay("GROUP_BAN_COND", g=c.group(grp), c=c.clause(k), roster=roster), 2,
             rid=c.rid("rg"), head=Lit(d.allow, ("?X",), neg=True),
             body=(Lit("grp", ("?X", grp)), lit(k)), prio=c.pr(3, 2)),
        _ctx_on(c, k),
    ], Probe("", (a, cc, alt), "CONFLICT", c.ns, "members banned while the condition holds"))
    b2 = Beat("join", [
        _hev(c, "ADD", "join_c", c.hsay("JOIN", e=c.name(cc), g=c.group(grp)), 2,
             rid=c.rid(f"g_{cc}"), head=Lit("grp", (cc, grp)), prio=1),
    ], Probe("", (a, cc, alt), "ADD", c.ns, "c joins the group and inherits the ban"))
    b3 = Beat("clear", [_ctx_off(c, k)],
              Probe("", (a, cc, alt), "CONDITION", c.ns, "condition off: everyone licensed again"))
    b4 = Beat("leave", [
        _ctx_on(c, k),
        _hev(c, "RETRACT", "leave_a", c.hsay("LEAVE", e=c.name(a), g=c.group(grp)), 2,
             rid=c.rid(f"g_{a}"), instances=((a, grp),)),
    ], Probe("", (a, cc, alt), "RETRACT", c.ns, "a leaves the group as the condition returns"))
    return MotifPlan("group_dynamics", [b0, b1, b2, b3, b4], facts, (a, b, cc, alt))


# --------------------------------------------------------------------------
# H4  speaker hierarchy beats recency
# --------------------------------------------------------------------------

def h_hierarchy(c: _HCtx, ents, ctxs, grp) -> MotifPlan:
    d, x, alt, z = c.dom, ents[0], ents[1], ents[2]
    b0 = Beat("open", [_allow_ev(c, x, "allow_x"), _allow_ev(c, alt, "allow_alt")],
              Probe("", (x, alt), "ADD", c.ns, "baseline"))
    b1 = Beat("secban", [
        _hev(c, "CONFLICT", "sec_ban", c.hsay("SEC_BAN", e=c.name(x)), 3,
             rid=c.rid("rsec"), head=_deny(d, x), prio=c.pr(3, 3)),
    ], Probe("", (x, alt), "CONFLICT", c.ns, "top authority bans x"))
    b2 = Beat("lead_default", [
        _hev(c, "ADD", "lead_default", c.hsay("LEAD_DEFAULT", e=c.name(x)), 2,
             rid=c.rid("rlead"), head=_allow(d, x), prio=c.pr(5, 2)),
    ], Probe("", (x, alt), "CONFLICT", c.ns, "lower authority says the opposite later: still banned"))
    b3 = Beat("lift", [
        _hev(c, "RETRACT", "lift", c.hsay("LIFT", e=c.name(x)), 3,
             rid=c.rid("rsec"), instances=((x,),), tags=("refable:LIFT",)),
        _hev(c, "CONFLICT", "lead_ban_alt", c.say("ADD_BAN", e=c.name(alt)), 2,
             rid=c.rid("rlalt"), head=_deny(d, alt), prio=c.pr(7, 2)),
    ], Probe("", (x, alt), "RETRACT", c.ns, "ban lifted: the lead's default now governs x"))
    b4 = Beat("lead_ban", [
        _hev(c, "CONFLICT", "lead_ban_x", c.say("SUPERSEDE", e=c.name(x)), 2,
             rid=c.rid("rlx"), head=_deny(d, x), prio=c.pr(9, 2)),
        _allow_ev(c, z, "allow_z"),
    ], Probe("", (x, alt, z), "CONFLICT", c.ns, "the lead now bans x itself"))
    return MotifPlan("hierarchy", [b0, b1, b2, b3, b4], [], (x, alt, z))


# --------------------------------------------------------------------------
# H5  stale reminders from people without authority
# --------------------------------------------------------------------------

def h_stale_reminder(c: _HCtx, ents, ctxs, grp) -> MotifPlan:
    d, x, alt = c.dom, ents[0], ents[1]
    b0 = Beat("open", [_allow_ev(c, x, "allow_x"), _allow_ev(c, alt, "allow_alt")],
              Probe("", (x, alt), "ADD", c.ns, "baseline"))
    b1 = Beat("secban", [
        _hev(c, "CONFLICT", "sec_ban", c.hsay("SEC_BAN", e=c.name(x)), 3,
             rid=c.rid("rsec"), head=_deny(d, x), prio=c.pr(3, 3)),
    ], Probe("", (x, alt), "CONFLICT", c.ns, "x banned"))
    b2 = Beat("chatter", [], Probe("", (x, alt), "NOISE", c.ns, "stale reminders about x: still banned"),
              noise=[c.noise("stale_echo", x), c.noise("praise", x)])
    b3 = Beat("lift", [
        _hev(c, "RETRACT", "lift", c.hsay("LIFT", e=c.name(x)), 3, rid=c.rid("rsec"), instances=((x,),), tags=("refable:LIFT",)),
        _hev(c, "CONFLICT", "lead_ban_alt", c.say("ADD_BAN", e=c.name(alt)), 2,
             rid=c.rid("rlalt"), head=_deny(d, alt), prio=c.pr(5, 2)),
    ], Probe("", (x, alt), "RETRACT", c.ns, "x lifted while hearsay says otherwise"),
              noise=[c.noise("hearsay", x)])
    return MotifPlan("stale_reminder", [b0, b1, b2, b3], [], (x, alt))


# --------------------------------------------------------------------------
# H6  retire -> reinstate -> conditionalise
# --------------------------------------------------------------------------

def h_reinstate_arc(c: _HCtx, ents, ctxs, grp) -> MotifPlan:
    d, x, alt, z = c.dom, ents[0], ents[1], ents[2]
    k = ctxs[0]
    b0 = Beat("open", [_allow_ev(c, x, "allow_x"), _allow_ev(c, alt, "allow_alt")],
              Probe("", (x, alt), "ADD", c.ns, "baseline"))
    b1 = Beat("retire", [
        _hev(c, "SUPERSEDE", "retire", c.say("SUPERSEDE", e=c.name(x)),
             rid=c.rid(f"r_{x}"), head=_deny(d, x), body=(), prio=c.pr(3)),
    ], Probe("", (x, alt), "SUPERSEDE", c.ns, "x retired"))
    b2 = Beat("reverse", [
        _hev(c, "SUPERSEDE", "reverse", c.hsay("REVERSE", e=c.name(x)),
             rid=c.rid(f"r_{x}"), head=_allow(d, x), body=(), prio=c.pr(3), tags=("refable:REVERSE",)),
    ], Probe("", (x, alt), "SUPERSEDE", c.ns, "retirement reversed"))
    b3 = Beat("condban", [
        _hev(c, "CONFLICT", "condban", c.say("CONFLICT", e=c.name(x), c=c.clause(k)),
             rid=c.rid("rbx"), head=_deny(d, x), body=(lit(k),), prio=c.pr(5)),
        _ctx_on(c, k),
    ], Probe("", (x, alt), "CONDITION", c.ns, "x banned under the condition"))
    b4 = Beat("clear", [
        _ctx_off(c, k),
        _hev(c, "CONFLICT", "ban_alt", c.say("ADD_BAN", e=c.name(alt)),
             rid=c.rid("rbalt"), head=_deny(d, alt), prio=c.pr(5)),
    ], Probe("", (x, alt), "CONDITION", c.ns, "condition off: x is the only licensed option"))
    b5 = Beat("retrigger", [_ctx_on(c, k), _allow_ev(c, z, "allow_z")],
              Probe("", (x, alt, z), "CONDITION", c.ns, "condition back: x banned, z licensed"))
    return MotifPlan("reinstate_arc", [b0, b1, b2, b3, b4, b5], [], (x, alt, z))


# --------------------------------------------------------------------------
# H7  proposals and hearsay that never become rules
# --------------------------------------------------------------------------

def h_proposal_noise(c: _HCtx, ents, ctxs, grp) -> MotifPlan:
    d, y, alt = c.dom, ents[0], ents[1]
    b0 = Beat("open", [_allow_ev(c, y, "allow_y"), _allow_ev(c, alt, "allow_alt")],
              Probe("", (y, alt), "ADD", c.ns, "baseline"))
    b1 = Beat("float", [], Probe("", (y, alt), "NOISE", c.ns, "proposal and question about y: no change"),
              noise=[c.noise("proposal", y), c.noise("question", y)])
    b2 = Beat("ban_alt", [
        _hev(c, "CONFLICT", "ban_alt", c.say("ADD_BAN", e=c.name(alt)),
             rid=c.rid("rbalt"), head=_deny(d, alt), prio=c.pr(3)),
    ], Probe("", (y, alt), "CONFLICT", c.ns, "y is the only licensed option despite the chatter"),
              noise=[c.noise("hearsay", y), c.noise("other_team", y)])
    b3 = Beat("echo_alt", [], Probe("", (y, alt), "NOISE", c.ns, "stale reminder about alt: still banned"),
              noise=[c.noise("rescind", y), c.noise("stale_echo", alt)])
    return MotifPlan("proposal_noise", [b0, b1, b2, b3], [], (y, alt))


HARD_MOTIFS = {
    # name -> (builder, entities, contexts, groups)
    "ctx_flipflop": (h_ctx_flipflop, 3, 1, 0),
    "alias": (h_alias, 3, 0, 0),
    "group_dynamics": (h_group_dynamics, 4, 1, 1),
    "hierarchy": (h_hierarchy, 3, 0, 0),
    "stale_reminder": (h_stale_reminder, 2, 0, 0),
    "reinstate_arc": (h_reinstate_arc, 3, 1, 0),
    "proposal_noise": (h_proposal_noise, 2, 0, 0),
}
