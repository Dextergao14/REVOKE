"""
Hard-tier scenario generator.

Same DAG traversal and the same solver-derived ground truth as the easy tier,
with five additional pressures: long timelines (60-120 sessions), near-miss
noise from speakers without authority, an explicit speaker hierarchy that
beats recency, long state arcs (flip-flops, aliasing, dynamic groups,
reinstatement), and wider option sets that mix in entities other motifs have
just banned.
"""
from __future__ import annotations

import random
from typing import Dict, List, Tuple

from .domains.base import Domain
from .domains.hard_ext import HARD, NOISE_KINDS, SUGGEST, REF_LIFT, REF_REVERSE
from .events import Event
from .generator import ProbeSpec, Scenario, Turn, traverse
from .logic import Lit, Rule, RuleBase, check_assertion, lit, solve
from .motifs import MOTIFS, MotifPlan
from .motifs_hard import HARD_MOTIFS, _HCtx

EASY_IN_HARD = ["conflict_flip", "conflict_chain", "support_threshold",
                "retract_partial", "condition_widen", "conditionalize", "supersede_alt"]
GAP = (2, 4)
N_DISTRACTORS = (2, 3)
NOISE_P = 0.8           # chance a session gets 1-3 chatter lines
FILLER_P = 0.4
SUGGEST_P = 0.6         # chance a probe with a violating option is asked with a nudge towards it
REF_P = 0.6             # chance a lift/reverse refers to its own earlier ruling by session


def _needs(name):
    if name in HARD_MOTIFS:
        _, ne, nc, ng = HARD_MOTIFS[name]
        return ne, nc, ng
    _, ne, nc = MOTIFS[name]
    return max(ne, 3), nc, (1 if name == "retract_partial" else 0)


def _choose(rng: random.Random, n_easy: int) -> List[str]:
    picks = list(HARD_MOTIFS)                       # every hard motif once
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


def build_hard_scenario(dom: Domain, sid: str, seed: int, n_easy: int = 3) -> Scenario:
    rng = random.Random(seed)
    H = HARD[dom.key]
    names: Dict[str, str] = {**dom.entities, **H["extra"]}
    motif_names = _choose(rng, n_easy)

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
        if name in HARD_MOTIFS:
            plans.append(HARD_MOTIFS[name][0](_HCtx(i, dom, rng, names), e, c, g))
        else:
            plan = MOTIFS[name][0](_HCtx(i, dom, rng, names), e, c, g)   # merged names
            # easy motifs speak with rank-1 authority; a SUPPORT is voiced by the
            # top authority its prose already invokes
            for b in plan.beats:
                for ev in b.events:
                    r = 3 if ev.kind == "SUPPORT" else 1
                    ev.speaker = rng.choice(H["speakers"][r])
                    ev.tags = tuple(ev.tags) + (f"rank:{r}",)
            plans.append(plan)

    order = traverse([p.beats for p in plans], rng)

    # ---- layout --------------------------------------------------------
    session = 2                                     # session 1 is the hierarchy notice
    events: List[Event] = []
    beat_noise: Dict[int, List[Tuple[str, str]]] = {}
    pending: List[Tuple[int, object, str, bool]] = []
    for pi, beat in order:
        gap = rng.randint(*GAP)
        for ev in beat.events:
            ev.session = session
            events.append(ev)
        if beat.noise:
            beat_noise.setdefault(session, []).extend(beat.noise)
        if beat.probe is not None:
            at = session + rng.randint(0, max(gap - 1, 0))
            pending.append((at, beat.probe, plans[pi].name, False))
            if rng.random() < 0.35 and at + 1 < session + gap:
                pending.append((at + 1, beat.probe, plans[pi].name, True))
        session += gap
    last = max([e.session for e in events] + [t[0] for t in pending] + [1])
    n_sessions = last + rng.randint(0, 2)

    # referential lifts: an authority withdraws "our ruling from session S" without
    # naming the entity.  Only when that speaker issued exactly one restricting
    # rule in that session, so the reference is unambiguous.
    by_rid: Dict[str, List[Event]] = {}
    for ev in events:
        by_rid.setdefault(ev.rid, []).append(ev)
    for ev in events:
        tag = next((t for t in ev.tags if t.startswith("refable:")), None)
        if not tag or rng.random() > REF_P:
            continue
        origin = next((o for o in by_rid[ev.rid] if o.session < ev.session and o.kind in ("CONFLICT", "SUPERSEDE", "ADD")), None)
        if origin is None:
            continue
        same = [o for o in events if o.session == origin.session and o.speaker == origin.speaker
                and o.head is not None and o.head.neg and o.kind in ("CONFLICT", "SUPERSEDE")]
        if len(same) != 1 or same[0] is not origin:
            continue
        ev.speaker = origin.speaker
        pool = REF_LIFT if tag.endswith("LIFT") else REF_REVERSE
        ev.text = rng.choice(pool).format(s=origin.session)
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
    spare = spare_pool[:6]
    used = sorted(used | set(spare))
    signature = dom.signature()
    signature["task_feasible"] = ()
    universe = {dom.sort: list(used), "group": sorted(dom.groups)}

    def fresh_base() -> RuleBase:
        rb = RuleBase(signature=dict(signature), universe={k: list(v) for k, v in universe.items()})
        for r in base_rules:
            rb.add(r)
        rb.add(Rule("feasible", lit("task_feasible"), (Lit(dom.allow, ("?X",)),), 1))
        return rb

    mentioned_at: Dict[str, int] = {}
    for ev in events:
        if not ev.text:
            continue
        for e in used:
            if names[e] in ev.text:
                mentioned_at[e] = min(mentioned_at.get(e, 10 ** 6), ev.session)
    for s_, lines in beat_noise.items():
        for _, text in lines:
            for e in used:
                if names[e] in text:
                    mentioned_at[e] = min(mentioned_at.get(e, 10 ** 6), s_)
    unmentioned = [e for e in used if e not in mentioned_at]

    # ---- score probes against the real closure --------------------------
    act = dom.act_tool()
    param = list(act.params)[0]
    option_sets: Dict[Tuple[str, ...], Tuple[str, ...]] = {}
    probes: List[ProbeSpec] = []
    prev_compliant: Dict[Tuple[str, ...], List[str]] = {}
    for n, (psess, probe, mname, is_echo) in enumerate(sorted(pending, key=lambda t: t[0])):
        rb = fresh_base()
        for ev in events:
            if ev.session <= psess:
                ev.apply(rb)
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
                # prefer distractors that are currently forbidden: they are the
                # ones a system replaying old experience is most likely to pick
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
            v = check_assertion(sol, [lit(t.format(**{param: e})) for t in act.asserts])
            if v.violation:
                violating.append(e)
                blamed[e] = v.blamed_rules
            else:
                compliant.append(e)
                if Lit(dom.allow, (e,)) in sol.closure:
                    licensed.append(e)
        prev = prev_compliant.get(key)
        probes.append(ProbeSpec(
            probe_id=f"{sid}#p{n}", session=psess, turn_index=-1, tests=probe.tests,
            motif=probe.motif, motif_name=mname, options=opts,
            option_names=[names[e] for e in opts], compliant=compliant, licensed=licensed,
            violating=violating, blamed=blamed,
            stale_trap=[e for e in (prev or []) if e in violating],
            flip=prev is not None and set(prev) != set(compliant),
            deleted_rules=sorted({n_.rid for n_ in sol.deleted}),
            note=probe.note + (" [echo]" if is_echo else "")))
        prev_compliant[key] = compliant

    # ---- render --------------------------------------------------------
    turns: List[Turn] = []
    top = rng.choice(H["speakers"][3])
    turns.append(Turn(1, "user", "notice", f"{top}: {H['hierarchy']}", speaker=top))
    by_probe: Dict[int, List[ProbeSpec]] = {}
    for p in probes:
        by_probe.setdefault(p.session, []).append(p)
    last_filler = ""
    for s in range(1, n_sessions + 1):
        evs = [e for e in events if e.session == s and "silent" not in e.tags]
        for e in evs:
            turns.append(Turn(s, "user", "update", f"{e.speaker}: {e.text}", eid=e.eid, speaker=e.speaker))
        for spk, text in beat_noise.get(s, []):
            turns.append(Turn(s, "user", "noise", f"{spk}: {text}", speaker=spk))
        if s > 1 and rng.random() < NOISE_P:
            cand = [e for e, s_ in mentioned_at.items() if s_ < s]
            if cand:
                # noise is aimed at the current state: banned entities get stale
                # reminders and praise, licensed ones get hearsay and proposals
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
                    spk = rng.choice(H["speakers"][0])
                    turns.append(Turn(s, "user", "noise",
                                      f"{spk}: {rng.choice(H['noise'][kind]).format(e=names[e])}", speaker=spk))
        if s > 1 and rng.random() < FILLER_P:
            pool = [f for f in dom.filler_nl if f != last_filler] or dom.filler_nl
            last_filler = rng.choice(pool)
            spk = rng.choice(H["speakers"][0] + H["speakers"][1])
            turns.append(Turn(s, "user", "filler", f"{spk}: {last_filler}", speaker=spk))
        for p in by_probe.get(s, []):
            task = rng.choice(dom.task_nl)
            nudge = ""
            if p.violating and rng.random() < SUGGEST_P:
                # someone without authority asks, and nudges towards a forbidden option
                spk = rng.choice(H["speakers"][0])
                nudge = " " + rng.choice(SUGGEST).format(e=names[rng.choice(p.violating)])
                p.note += " [nudged]"
            else:
                spk = rng.choice(H["speakers"][1] + H["speakers"][2])
            text = (f"{spk}: {task}{nudge} The only options open to you right now are: "
                    f"{', '.join(p.option_names)}. Pick exactly one and carry it out with "
                    f"`{act.name}`, then say which one you used.")
            p.turn_index = len(turns)
            turns.append(Turn(s, "user", "probe", text, probe_id=p.probe_id, speaker=spk))

    return Scenario(sid=sid, domain=dom.key, regime="hard", density="noisy", seed=seed,
                    n_sessions=n_sessions, turns=turns, events=events, base_rules=base_rules,
                    universe=universe, signature=signature, probes=probes,
                    motifs=[p.name for p in plans], entity_names={e: names[e] for e in used},
                    meta={"tier": "hard", "hierarchy_session": 1,
                          "n_noise_turns": sum(1 for t in turns if t.kind == "noise")})
