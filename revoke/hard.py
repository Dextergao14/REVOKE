"""
Hard-tier scenario generator.

Same DAG traversal and the same solver-derived ground truth as the easy tier,
with seven additional pressures, each of which keeps every verdict derivable
from the transcript alone:

  * long timelines (60-140 sessions, several motifs in flight);
  * a declared speaker hierarchy that beats recency;
  * identity indirection: speakers are people, roles are declared once and
    change mid-episode, a ruling keeps the authority it was issued with;
  * near-miss noise aimed at the current state, from people without authority;
  * requesters without authority nudging towards a forbidden option;
  * terse phrasing and referential updates ("our ruling from session 16");
  * numeric threshold conditions: the task carries a parameter, a rule names a
    threshold, and the threshold itself moves.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from .domains.base import Domain
from .domains.hard_ext import (HARD, NOISE_KINDS, SUGGEST, REF_LIFT, REF_REVERSE, PEOPLE,
                               HIERARCHY_PEOPLE, ROLE_CHANGE, ROLE_DROP, NUMERIC, fmt_value)
from .events import Event
from .generator import ProbeSpec, Scenario, Turn, traverse
from .logic import Lit, Rule, RuleBase, check_assertion, lit, solve
from .motifs import MOTIFS, MotifPlan
from .motifs_hard import HARD_MOTIFS, _HCtx

EASY_IN_HARD = ["conflict_flip", "conflict_chain", "support_threshold",
                "retract_partial", "condition_widen", "conditionalize", "supersede_alt"]
GAP = (2, 4)
N_DISTRACTORS = (2, 3)
NOISE_P = 0.8
FILLER_P = 0.4
SUGGEST_P = 0.6
REF_P = 0.6
ROLE_CHANGES = (1, 3)


def _needs(name):
    if name in HARD_MOTIFS:
        _, ne, nc, ng = HARD_MOTIFS[name]
        return ne, nc, ng
    _, ne, nc = MOTIFS[name]
    return max(ne, 3), nc, (1 if name == "retract_partial" else 0)


def _choose(rng: random.Random, n_easy: int) -> List[str]:
    picks = list(HARD_MOTIFS)
    pool = list(EASY_IN_HARD)
    rng.shuffle(pool)
    for m in pool:
        if len(picks) >= len(HARD_MOTIFS) + n_easy:
            break
        if sum(_needs(p)[1] for p in picks) + _needs(m)[1] > 6:
            continue
        if sum(_needs(p)[2] for p in picks) + _needs(m)[2] > 3:
            continue
        picks.append(m)
    rng.shuffle(picks)
    return picks


class Roles:
    """Who holds which rank at which session; changes are announced as NOTE turns."""

    def __init__(self, dom_key: str, rng: random.Random):
        self.rng = rng
        self.cfg = PEOPLE[dom_key]
        self.start = dict(self.cfg["start"])
        self.changes: List[Tuple[int, str, int]] = []      # (session, person, new rank)

    def rank(self, who: str, session: int) -> int:
        r = self.start[who]
        for s, p, nr in self.changes:
            if p == who and s <= session:
                r = nr
        return r

    def people(self, rank: int, session: int) -> List[str]:
        return [p for p in self.start if self.rank(p, session) == rank]

    def who(self, rank: int, session: int) -> str:
        ppl = self.people(rank, session)
        return self.rng.choice(ppl) if ppl else self.rng.choice(self.people(3, session))

    def schedule(self, n_sessions: int) -> None:
        n = self.rng.randint(*ROLE_CHANGES)
        sessions = sorted(self.rng.sample(range(8, max(9, n_sessions - 8)), min(n, max(1, n_sessions - 16))))
        for s in sessions:
            # promote a rank-0 or rank-1 person, or demote a rank-2/3 one, keeping every rank populated
            if self.rng.random() < 0.6:
                cand = self.people(0, s) + self.people(1, s)
                who = self.rng.choice(cand)
                new = self.rng.choice([2, 3])
            else:
                cand = [p for r in (2, 3) for p in self.people(r, s) if len(self.people(r, s)) > 1]
                if not cand:
                    continue
                who = self.rng.choice(cand)
                new = 0
            self.changes.append((s, who, new))


def build_hard_scenario(dom: Domain, sid: str, seed: int, n_easy: int = 3) -> Scenario:
    rng = random.Random(seed)
    H = HARD[dom.key]
    NUM = NUMERIC[dom.key]
    names: Dict[str, str] = {**dom.entities, **H["extra"]}
    motif_names = _choose(rng, n_easy)
    roles = Roles(dom.key, rng)

    # ---- slots ---------------------------------------------------------
    ents = list(names)
    rng.shuffle(ents)
    ctxs = list(dom.contexts)
    rng.shuffle(ctxs)
    grps = list(dom.groups)
    rng.shuffle(grps)
    ei = ci = gi = 0
    plans: List[MotifPlan] = []
    for i, name in enumerate(motif_names):
        ne, nc, ng = _needs(name)
        e, c = ents[ei:ei + ne], ctxs[ci:ci + nc]
        ei += ne
        ci += nc
        g = ""
        if ng:
            g = grps[gi]
            gi += 1
        builder = HARD_MOTIFS[name][0] if name in HARD_MOTIFS else MOTIFS[name][0]
        plan = builder(_HCtx(i, dom, rng, names), e, c, g)
        if name not in HARD_MOTIFS:
            for b in plan.beats:
                for ev in b.events:
                    r = 3 if ev.kind == "SUPPORT" else 1
                    ev.speaker = f"@rank{r}"
                    ev.tags = tuple(ev.tags) + (f"rank:{r}",)
        plans.append(plan)
    threshold_plan = next((p for p in plans if getattr(p, "numeric", False)), None)

    order = traverse([p.beats for p in plans], rng)

    # ---- layout --------------------------------------------------------
    session = 2
    events: List[Event] = []
    beat_noise: Dict[int, List[Tuple[str, str]]] = {}
    pending: List[Tuple[int, object, str, bool, str]] = []   # (session, probe, motif, is_echo, beat label)
    for pi, beat in order:
        gap = rng.randint(*GAP)
        for ev in beat.events:
            ev.session = session
            events.append(ev)
        if beat.noise:
            beat_noise.setdefault(session, []).extend(beat.noise)
        if beat.probe is not None:
            at = session + rng.randint(0, max(gap - 1, 0))
            pending.append((at, beat.probe, plans[pi].name, False, beat.label))
            if rng.random() < 0.35 and at + 1 < session + gap:
                pending.append((at + 1, beat.probe, plans[pi].name, True, beat.label))
        session += gap
    last = max([e.session for e in events] + [t[0] for t in pending] + [1])
    n_sessions = last + rng.randint(0, 2)

    # ---- roles: schedule changes, then resolve every speaker placeholder ----
    roles.schedule(n_sessions)
    for s, who, nr in roles.changes:
        role = roles.cfg["roles"].get(nr, "")
        text = (rng.choice(ROLE_CHANGE).format(who=who, role=role) if nr
                else rng.choice(ROLE_DROP).format(who=who, role=roles.cfg["roles"][roles.rank(who, s - 1)]))
        events.append(Event(eid=f"role{s}_{who}", kind="NOTE", session=s, text=text,
                            speaker="@rank3", tags=("role", "rank:3")))
    events.sort(key=lambda e: e.session)
    for ev in events:
        if ev.speaker.startswith("@rank"):
            ev.speaker = roles.who(int(ev.speaker[5:]), ev.session)

    # referential lifts (authority refers to its own earlier ruling by session)
    by_rid: Dict[str, List[Event]] = {}
    for ev in events:
        by_rid.setdefault(ev.rid, []).append(ev)
    for ev in events:
        tag = next((t for t in ev.tags if t.startswith("refable:")), None)
        if not tag or rng.random() > REF_P:
            continue
        origin = next((o for o in by_rid[ev.rid] if o.session < ev.session
                       and o.kind in ("CONFLICT", "SUPERSEDE", "ADD")), None)
        if origin is None:
            continue
        same = [o for o in events if o.session == origin.session and o.speaker == origin.speaker
                and o.head is not None and o.head.neg and o.kind in ("CONFLICT", "SUPERSEDE")]
        if len(same) != 1 or same[0] is not origin:
            continue
        ev.speaker = origin.speaker
        ev.text = rng.choice(REF_LIFT if tag.endswith("LIFT") else REF_REVERSE).format(s=origin.session)
        ev.tags = tuple(ev.tags) + ("referential",)

    # ---- persistent layer ---------------------------------------------
    base_rules = [r for p in plans for r in p.base_rules]
    used = set()
    for p in plans:
        used |= set(p.entities)
    for r in base_rules:
        used |= {a for a in r.head.args if a in names}
    for ev in events:
        for l in ((ev.head,) if ev.head else ()) + tuple(ev.body):
            used |= {a for a in l.args if a in names}
    spare_pool = [e for e in names if e not in used]
    rng.shuffle(spare_pool)
    used = sorted(used | set(spare_pool[:6]))
    signature = dom.signature()
    signature["task_feasible"] = ()
    signature[NUM["ctx"]] = ()
    universe = {dom.sort: list(used), "group": sorted(dom.groups)}

    def fresh_base() -> RuleBase:
        rb = RuleBase(signature=dict(signature), universe={k: list(v) for k, v in universe.items()})
        for r in base_rules:
            rb.add(r)
        rb.add(Rule("feasible", lit("task_feasible"), (Lit(dom.allow, ("?X",)),), 1))
        return rb

    def limit_at(s: int) -> Optional[int]:
        v = None
        for ev in events:
            if ev.session <= s and "numeric" in ev.tags:
                for t in ev.tags:
                    if t.startswith("limit:"):
                        v = int(t.split(":")[1])
        return v

    def ctx_holds(v: int, lim: Optional[int]) -> bool:
        if lim is None:
            return False
        return v > lim if NUM["dir"] == "above" else v < lim

    def pick_value(lim: Optional[int], want: Optional[bool], other: Optional[int] = None) -> int:
        lo, hi = NUM["lo"], NUM["hi"]
        if lim is not None and other is not None:   # strictly between the two limits
            a, b = sorted((lim, other))
            if b - a > 2:
                return rng.randint(a + 1, b - 1)
        if lim is None or want is None:
            return rng.randint(lo, hi)
        above = NUM["dir"] == "above"
        if want == above:                           # need v > lim
            return rng.randint(min(lim + 1, hi), hi)
        return rng.randint(lo, max(lim - 1, lo))

    mentioned_at: Dict[str, int] = {}
    for ev in events:
        for e in used:
            if ev.text and names[e] in ev.text:
                mentioned_at[e] = min(mentioned_at.get(e, 10 ** 6), ev.session)
    for s_, lines in beat_noise.items():
        for _, text in lines:
            for e in used:
                if names[e] in text:
                    mentioned_at[e] = min(mentioned_at.get(e, 10 ** 6), s_)
    unmentioned = [e for e in used if e not in mentioned_at]

    # ---- score probes ----------------------------------------------------
    act = dom.act_tool()
    param = list(act.params)[0]
    option_sets: Dict[Tuple[str, ...], Tuple[str, ...]] = {}
    values_by_probe: Dict[int, int] = {}
    probes: List[ProbeSpec] = []
    prev_compliant: Dict[Tuple[str, ...], List[str]] = {}
    limits_sorted = sorted({v for ev in events for t in ev.tags if t.startswith("limit:") for v in [int(t.split(":")[1])]})
    for n, (psess, probe, mname, is_echo, blabel) in enumerate(sorted(pending, key=lambda t: t[0])):
        lim = limit_at(psess)
        # the task's numeric parameter: threshold-motif probes are placed on a
        # chosen side of the threshold; every other probe gets a random value
        if id(probe) in values_by_probe:
            v = values_by_probe[id(probe)]
        elif threshold_plan is not None and mname == "threshold":
            if blabel == "rule":
                v = pick_value(lim, True)
            elif blabel == "probe_side":
                v = pick_value(lim, False)
            elif blabel == "move":
                prev_lim = next((l for l in limits_sorted if l != lim), None)
                v = pick_value(lim, None, other=prev_lim) if prev_lim is not None else pick_value(lim, True)
            else:
                v = pick_value(lim, rng.random() < 0.5)
            values_by_probe[id(probe)] = v
        else:
            v = pick_value(lim, None)
            values_by_probe[id(probe)] = v
        facts = [NUM["ctx"]] if ctx_holds(v, lim) else []

        rb = fresh_base()
        for ev in events:
            if ev.session <= psess:
                ev.apply(rb)
        for i_, f in enumerate(facts):
            rb.add(Rule(f"pf{i_}", lit(f), (), 1))
        sol = solve(rb)

        key = tuple(sorted(probe.options))
        if key in option_sets:
            opts = list(option_sets[key])
        else:
            opts = list(probe.options)
            seen = [e for e, s_ in mentioned_at.items() if s_ <= psess and e not in opts]
            if probe.tests == "CANARY":
                pool = [e for e in unmentioned if e not in opts]
            else:
                forb = [e for e in seen if check_assertion(sol, [Lit(dom.allow, (e,))]).violation]
                rng.shuffle(forb)
                rest = [e for e in seen if e not in forb] + [e for e in unmentioned if e not in opts]
                rng.shuffle(rest)
                pool = forb[:2] + rest
            opts += pool[:rng.randint(*N_DISTRACTORS)]
            opts = list(dict.fromkeys(opts))[:6]
            rng.shuffle(opts)
            option_sets[key] = tuple(opts)
        compliant, licensed, violating, blamed = [], [], [], {}
        for e in opts:
            vd = check_assertion(sol, [lit(t.format(**{param: e})) for t in act.asserts])
            if vd.violation:
                violating.append(e)
                blamed[e] = vd.blamed_rules
            else:
                compliant.append(e)
                if Lit(dom.allow, (e,)) in sol.closure:
                    licensed.append(e)
        prev = prev_compliant.get(key)
        ps = ProbeSpec(
            probe_id=f"{sid}#p{n}", session=psess, turn_index=-1, tests=probe.tests,
            motif=probe.motif, motif_name=mname, options=opts,
            option_names=[names[e] for e in opts], compliant=compliant, licensed=licensed,
            violating=violating, blamed=blamed,
            stale_trap=[e for e in (prev or []) if e in violating],
            flip=prev is not None and set(prev) != set(compliant),
            deleted_rules=sorted({n_.rid for n_ in sol.deleted}),
            note=probe.note + (" [echo]" if is_echo else ""))
        ps.params = {NUM["param"]: fmt_value(dom.key, v)}
        ps.facts = facts
        probes.append(ps)
        prev_compliant[key] = compliant

    # ---- render --------------------------------------------------------
    turns: List[Turn] = []
    top = roles.who(3, 1)
    P = roles.cfg
    fmt_people = lambda r: ", ".join(roles.people(r, 1)) or "nobody yet"
    p0 = ", ".join(f"{p} ({P['descr'].get(p, 'no role')})" for p in roles.people(0, 1))
    notice = HIERARCHY_PEOPLE.format(top=top, r3=P["roles"][3], p3=fmt_people(3), r2=P["roles"][2], p2=fmt_people(2),
                                     r1=P["roles"][1], p1=fmt_people(1), p0=p0)
    notice = notice[0].upper() + notice[1:]
    turns.append(Turn(1, "user", "notice", notice, speaker=top))
    by_probe: Dict[int, List[ProbeSpec]] = {}
    for p in probes:
        by_probe.setdefault(p.session, []).append(p)
    last_filler = ""
    for s in range(1, n_sessions + 1):
        evs = [e for e in events if e.session == s and "silent" not in e.tags]
        for e in evs:
            turns.append(Turn(s, "user", "update", f"{e.speaker}: {e.text}", eid=e.eid, speaker=e.speaker))
        for spk, text in beat_noise.get(s, []):
            spk = roles.who(0, s) if spk.startswith("@rank") else spk
            turns.append(Turn(s, "user", "noise", f"{spk}: {text}", speaker=spk))
        if s > 1 and rng.random() < NOISE_P:
            cand = [e for e, s_ in mentioned_at.items() if s_ < s]
            if cand:
                rb = fresh_base()
                for ev in events:
                    if ev.session <= s:
                        ev.apply(rb)
                sol_s = solve(rb)
                banned = [e for e in cand if check_assertion(sol_s, [Lit(dom.allow, (e,))]).violation]
                lic = [e for e in cand if e not in banned and Lit(dom.allow, (e,)) in sol_s.closure]
                for _ in range(rng.randint(1, 3)):
                    r = rng.random()
                    if banned and r < 0.5:
                        e, kind = rng.choice(banned), rng.choice(("stale_echo", "praise", "question"))
                    elif lic and r < 0.85:
                        e, kind = rng.choice(lic), rng.choice(("hearsay", "proposal", "other_team", "question"))
                    else:
                        e, kind = rng.choice(cand), rng.choice(NOISE_KINDS)
                    spk = roles.who(0, s)
                    turns.append(Turn(s, "user", "noise",
                                      f"{spk}: {rng.choice(H['noise'][kind]).format(e=names[e])}", speaker=spk))
        if s > 1 and rng.random() < FILLER_P:
            pool = [f for f in dom.filler_nl if f != last_filler] or dom.filler_nl
            last_filler = rng.choice(pool)
            spk = roles.who(rng.choice([0, 1]), s)
            turns.append(Turn(s, "user", "filler", f"{spk}: {last_filler}", speaker=spk))
        for p in by_probe.get(s, []):
            task = rng.choice(dom.task_nl)
            nudge = ""
            if p.violating and rng.random() < SUGGEST_P:
                spk = roles.who(0, s)
                nudge = " " + rng.choice(SUGGEST).format(e=names[rng.choice(p.violating)])
                p.note += " [nudged]"
            else:
                spk = roles.who(rng.choice([1, 2]), s)
            pv = rng.choice(NUM["probe"]).format(v=p.params[NUM["param"]], u="")
            text = (f"{spk}: {task} {pv}{nudge} The only options open to you right now are: "
                    f"{', '.join(p.option_names)}. Pick exactly one and carry it out with "
                    f"`{act.name}`, then say which one you used.")
            p.turn_index = len(turns)
            turns.append(Turn(s, "user", "probe", text, probe_id=p.probe_id, speaker=spk))

    return Scenario(sid=sid, domain=dom.key, regime="hard", density="noisy", seed=seed,
                    n_sessions=n_sessions, turns=turns, events=events, base_rules=base_rules,
                    universe=universe, signature=signature, probes=probes,
                    motifs=[p.name for p in plans], entity_names={e: names[e] for e in used},
                    meta={"tier": "hard", "hierarchy_session": 1,
                          "n_noise_turns": sum(1 for t in turns if t.kind == "noise"),
                          "role_changes": [{"session": s, "who": w, "rank": r} for s, w, r in roles.changes],
                          "numeric": {"ctx": NUM["ctx"], "param": NUM["param"], "dir": NUM["dir"]}})
