"""
Render a scenario as a minute book, padded to a token target.

The engine, the events and the ground truth are untouched.  This only decides
how the turns are laid out on the page: each session becomes a meeting with a
title, attendee lines, a notetaker artifact, and sections.  Where a turn goes is
decided by what it is, and that placement is itself part of the test:

  * rule events go under Decisions, attributed to whoever issued them;
  * chatter goes under Discussion, including the lines phrased as decisions by
    people with no authority to make one -- so the section header is a cue and
    the phrasing is a counter-cue, and only the speaker settles it;
  * the task goes under Action Items, asked by whoever is asking;
  * everything else on the agenda is Other Business, drawn from the
    combinatorial padder, and is what carries the transcript to its target.

Padding never mentions a governed entity and never uses the rule register, so it
cannot change the closure -- see `revoke.padding`.
"""
from __future__ import annotations

import random
from dataclasses import replace
from typing import Dict, List, Optional

from .domains.meetings import CORPUS
from .generator import Scenario, Turn
from .padding import Padder

_SC = CORPUS["scaffold"]
_FILL = CORPUS["filler"]
TOK = 4                                              # chars per token, approximate


def _tokens(turns: List[Turn]) -> int:
    return sum(len(t.text) + 1 for t in turns) // TOK


def render_minute_book(sc: Scenario, seed: int = 0,
                       target_tokens: int = 0,
                       attendee_names: Optional[List[str]] = None) -> Scenario:
    """Return a copy of `sc` whose turns are meeting minutes, padded to target."""
    rng = random.Random(seed or sc.seed)
    pad = Padder(rng, banned=list(sc.entity_names.values()))
    people = attendee_names or sorted({t.speaker for t in sc.turns if t.speaker})
    by_session: Dict[int, List[Turn]] = {}
    for t in sc.turns:
        by_session.setdefault(t.session, []).append(t)

    # how much filler each meeting needs to hit the target
    base = _tokens(sc.turns)
    n_meetings = max(len(by_session), 1)
    need = max(target_tokens - base, 0)
    per_meeting_chars = (need * TOK) // n_meetings

    out: List[Turn] = []
    seq = 0

    def add(session: int, kind: str, text: str, **kw) -> None:
        out.append(Turn(session, "user", kind, text, **kw))

    # agenda blocks are drawn without replacement and reshuffled only when the
    # pool runs dry, so no meeting repeats a block and the whole book repeats
    # one only after all sixty have been used
    pool: List[str] = []

    def agenda_block() -> List[str]:
        nonlocal pool
        if not pool:
            pool = list(_FILL["agenda_items"])
            rng.shuffle(pool)
        return pool.pop().split("\n")

    sessions = sorted(by_session.items())
    # the authority notice is a standing wiki page, not a meeting decision
    notice = next((t for ts in by_session.values() for t in ts if t.kind == "notice"), None)
    if notice is not None:
        add(notice.session, "meta", "### Tooling Governance: how decisions are made (wiki page, pinned)")
        out.append(notice)
        add(notice.session, "meta", "(End of wiki page. Meeting minutes follow.)")

    for n, (session, turns) in enumerate(sessions, 1):
        seq += 1
        mt = rng.choice(_SC["meeting_types"])
        present = rng.sample(people, min(len(people), rng.randint(4, 7)))
        add(session, "meta", f"### {mt['title'].format(n=seq)}  ({mt['cadence']})")
        for line in rng.sample(_SC["header_lines"], rng.randint(1, 3)):
            # {people} and {n} must agree: an attendee count that contradicts
            # the list it sits next to is the kind of detail that makes a
            # generated corpus read as generated
            if line.startswith("Chair:"):
                # a chair is one person, not the attendee list
                add(session, "meta", line.replace("{people}", present[0])
                    .replace("{n}", str(max(2, len(present) - 1))))
                continue
            if "{people}" in line and "{n}" in line:
                line = line.replace("{n}", str(len(present)), 1)
            elif line.startswith("Scheduled for"):
                line = line.replace("{n}", str(rng.choice((25, 30, 45, 50, 60))), 1)
                line = line.replace("{n}", str(rng.randint(3, 14)), 1)
            add(session, "meta", line.format(people=", ".join(present), n=rng.randint(2, 9)))
        if rng.random() < 0.25:
            add(session, "meta", rng.choice(_SC["ai_artifacts"]))

        rules = [t for t in turns if t.kind == "update"]
        chat = [t for t in turns if t.kind in ("noise", "filler")]
        probes = [t for t in turns if t.kind == "probe"]

        # -- Discussion: chatter and other business, shuffled as whole items so
        #    a multi-line agenda block keeps its internal order
        budget = per_meeting_chars
        chunks: List[List[Turn]] = [[t] for t in chat]
        while budget > 0:
            r = rng.random()
            if r < 0.12:
                lines = agenda_block()
            elif r < 0.9:
                lines = pad.block()
            else:
                lines = [pad.side()]
            chunks.append([Turn(session, "user", "pad", x) for x in lines])
            budget -= sum(len(x) for x in lines)
        if chunks:
            add(session, "meta", rng.choice(_SC["section_headers"]["discussion"]))
            rng.shuffle(chunks)
            for ch in chunks:
                out += [replace(t, session=session) for t in ch]

        # -- Decisions: the rule events, in the order they were issued
        if rules:
            add(session, "meta", rng.choice(_SC["section_headers"]["decisions"]))
            out += rules

        # -- Action items: the graded task, plus unrelated follow-ups
        if probes or rng.random() < 0.5:
            add(session, "meta", rng.choice(_SC["section_headers"]["actions"]))
            for _ in range(rng.randint(1, 3)):
                add(session, "pad", rng.choice(_FILL["action_items"]))
            for t in probes:
                out.append(t)
                add(session, "pad", pad.action())

    new = replace(sc, turns=out)
    # turn indices moved, so re-point every probe at its rendered turn
    pos = {t.probe_id: i for i, t in enumerate(out) if t.probe_id}
    for p in new.probes:
        p.turn_index = pos.get(p.probe_id, -1)
    new.meta = dict(sc.meta)
    new.meta.update({"format": "minute_book", "target_tokens": target_tokens,
                     "tokens": _tokens(out), "pad_turns": sum(1 for t in out if t.kind == "pad"),
                     "meta_turns": sum(1 for t in out if t.kind == "meta")})
    return new
