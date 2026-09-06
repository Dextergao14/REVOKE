"""Scenario -> benchmark item, and the blind view handed to agents."""
from __future__ import annotations

from typing import Dict, List

from .domains.base import Domain
from .generator import Scenario
from .logic import solve
from .verify import _rulebase_at

from .events import event_from_json
from .logic import Lit, Rule, RuleBase, lit as _lit

SECRET_FIELDS = ("compliant", "violating", "blamed", "stale_trap", "flip",
                 "deleted_rules", "note")


def scenario_to_item(sc: Scenario, dom: Domain) -> Dict:
    sessions: List[Dict] = []
    for s in range(1, sc.n_sessions + 1):
        ts = [t for t in sc.turns if t.session == s]
        if ts:
            sessions.append({"index": s, "turns": [
                {"kind": t.kind, "text": t.text,
                 **({"probe_id": t.probe_id} if t.probe_id else {})} for t in ts]})

    timeline = []
    for p in sc.probes:
        sol = solve(_rulebase_at(sc, p.session, dom.allow))
        timeline.append({
            "probe_id": p.probe_id, "session": p.session,
            "closure": sorted(str(l) for l in sol.closure),
            "extension": sorted({n.rid for n in sol.extension}),
            "deleted": sorted({n.rid for n in sol.deleted}),
        })

    act = dom.act_tool()
    return {
        "id": sc.sid,
        "domain": sc.domain,
        "sort": dom.sort,
        "allow": dom.allow,
        "goal": dom.goal,
        "contexts": sorted(dom.contexts),
        "universe": sc.universe,
        "base_rules": [{"rid": r.rid, "head": str(r.head),
                        "body": [str(b) for b in r.body], "prio": r.prio}
                       for r in sc.base_rules],
        "domain_title": dom.title,
        "regime": sc.regime,
        "density": sc.density,
        "seed": sc.seed,
        "motifs": sc.motifs,
        "n_sessions": sc.n_sessions,
        "sessions": sessions,
        "tools": [{"name": t.name, "params": t.params, "kind": t.kind,
                   "doc": t.doc} for t in dom.tools],
        "act_tool": act.name,
        "act_param": list(act.params)[0],
        "entity_names": sc.entity_names,
        "probes": [{
            "probe_id": p.probe_id, "session": p.session,
            "tests": p.tests, "motif": p.motif, "motif_name": p.motif_name,
            "options": p.options, "option_names": p.option_names,
            "compliant": p.compliant,
            "compliant_names": [dom.entities[e] for e in p.compliant],
            "licensed": p.licensed,
            "licensed_names": [dom.entities[e] for e in p.licensed],
            "violating": p.violating,
            "violating_names": [dom.entities[e] for e in p.violating],
            "blamed": p.blamed, "stale_trap": p.stale_trap,
            "flip": p.flip, "deleted_rules": p.deleted_rules, "note": p.note,
        } for p in sc.probes],
        "events": [e.to_json() for e in sc.events],
        "timeline": timeline,
    }


def blind(item: Dict) -> Dict:
    """The view an agent is allowed to see: no closure, no compliant set."""
    # the blind view carries only what an agent legitimately sees: the
    # transcript, the tool surface, and the option sets.  No rule vocabulary,
    # no universe, no base facts -- those would let a parser reconstruct
    # constraints the conversation is supposed to be the sole source of.
    out = {k: v for k, v in item.items()
           if k not in ("timeline", "events", "motifs", "base_rules", "allow",
                        "sort", "goal", "contexts", "universe", "seed")}
    out["probes"] = [{"probe_id": p["probe_id"], "session": p["session"],
                      "options": p["options"],
                      "option_names": p["option_names"]}
                     for p in item["probes"]]
    return out


# --------------------------------------------------------------------------
# grader-side reconstruction: rebuild the persistent layer from a full item
# --------------------------------------------------------------------------

_GRP_RE = None


def rulebase_at(item: Dict, session: int, allow: str) -> RuleBase:
    """Rebuild R_t from a full (non-blind) item, for independent re-grading."""
    sig = {allow: (item["sort"],), item["goal"]: (),
           "grp": (item["sort"], "group"), "task_feasible": ()}
    for c in item["contexts"]:
        sig[c] = ()
    rb = RuleBase(signature=sig, universe={k: list(v)
                                           for k, v in item["universe"].items()})
    for r in item["base_rules"]:
        rb.add(Rule(r["rid"], _lit(r["head"]),
                    tuple(_lit(b) for b in r["body"]), r["prio"]))
    rb.add(Rule("feasible", _lit("task_feasible"), (Lit(allow, ("?X",)),), 1))
    for d in item["events"]:
        e = event_from_json(d)
        if e.session <= session:
            e.apply(rb)
    return rb
