#!/usr/bin/env python3
"""Convert the v1 meetings corpus + revoke.padding into a schema-v2 corpus.

    python3 scripts/convert_meetings_corpus.py  -> revoke/domains/corpora/meetings.json

The meetings domain predates the corpus schema; this makes it a sixth scenario
for the long tier without touching revoke/domains/meetings.py, which the
existing pilot items still depend on.  Filler that uses the rule register is
dropped rather than rewritten, and the count of what was dropped is printed.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from revoke import padding as P                                   # noqa: E402
from revoke.domains.meetings import (CERT_MEETINGS, CONJ_MEETINGS, CORPUS, DERIVED_MEETINGS,  # noqa: E402
                                     HNL_MEETINGS, MEETINGS, NUMERIC_MEETINGS, TERSE_MEETINGS,
                                     TIER_RANK)
from validate_corpus import REGISTER                              # noqa: E402

DEC, CH, SC, FI, ORG = (CORPUS["decisions"], CORPUS["chatter"], CORPUS["scaffold"],
                        CORPUS["filler"], CORPUS["org"])


def clean(lst, where, dropped):
    keep = []
    for t in lst:
        if REGISTER.search(t):
            dropped.append((where, t[:60]))
        else:
            keep.append(t)
    return keep


def main() -> None:
    dropped = []
    nl = dict(MEETINGS.nl)
    nl["GROUP_BAN"] = nl["GROUP_BAN"] + ["Board ruling: nothing in {g} is to be used by any team."]
    nl["CONFLICT_WEAK"] = nl["CONFLICT_WEAK"] + [
        "Security's concern about {e} while {c} is recorded as advisory. The standing approval of "
        "{e} is not affected by it."]
    nl["SUPPORT_BAN"] = nl["SUPPORT_BAN"] + [
        "The Board has upgraded the {e} advisory to a prohibition; it outranks the earlier approval."]
    notice = ORG["authority_notice"]
    for lit, ph in (("The Tooling Review Board", "{r3}"), ("the engineering directors", "{r2}"),
                    ("the build teams", "{r1}")):
        notice = notice.replace(lit, ph, 1)
    hnl = {k: ([v] if isinstance(v, str) else list(v)) for k, v in HNL_MEETINGS.items()}
    # extra vocab slots the old padder generated inline
    slots = {
        "t": P.TEAMS, "te": P.ENG_TEAMS, "tb": P.BIZ_TEAMS, "j": P.PROJECTS, "a": P.ARTIFACTS,
        "u": P.CUSTOMERS, "m": P.METRICS, "city": P.CITIES, "v": P.VERBS,
        "n_meeting": ["15", "20", "25", "30", "40", "45", "50", "60"],
        "n_tickets_b": [str(x) for x in (7, 11, 14, 19, 23, 31, 38, 44, 52, 61)],
        "n_desks": [str(x) for x in (24, 30, 36, 42, 48, 60, 72, 90)],
        "n_floor": [str(x) for x in range(1, 9)],
        "ord_floor": ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"],
    }
    fams = {k: [t.replace("{n_tickets2}", "{n_tickets_b}") for t in clean(v, f"pad.{k}", dropped)]
            for k, v in P.FAMILIES.items()}
    c = {
        "key": "meetings",
        "title": MEETINGS.title,
        "setting": ("You are the tooling assistant for an engineering organisation, reading its "
                    "minute book: months of meeting minutes produced by an AI notetaker. The "
                    "Tooling Review Board decides which tools and vendors may be used; directors "
                    "and teams discuss, raise problems and occasionally overreach. When a piece of "
                    "work needs doing you run it through one approved tool."),
        "sort": MEETINGS.sort, "allow": MEETINGS.allow, "goal": MEETINGS.goal,
        "persona": MEETINGS.persona,
        "entities": {"prefix": "tl", "names": CORPUS["entities"]["entities"][:96],
                     "conditions": CORPUS["entities"]["conditions"],
                     "groups": CORPUS["entities"]["categories"]},
        "tools": {"read": [{"name": "read_register", "param": "topic",
                            "doc": "Read the tooling register entry for a topic."},
                           {"name": "list_tools", "param": "query",
                            "doc": "List every tool and vendor on file."}],
                  "act": {"name": "use_tool", "param": "tool",
                          "doc": "Run the requested work through a tool or vendor."}},
        "nl": nl,
        "task_nl": list(MEETINGS.task_nl),
        "filler_nl": clean(FI["side_lines"], "filler_nl", dropped),
        "hnl": hnl,
        "terse": TERSE_MEETINGS,
        "people": {"roles": {"3": "the Tooling Review Board", "2": "the engineering directors",
                             "1": "the build teams"},
                   "start": {p["name"]: TIER_RANK[p["tier"]] for p in ORG["people"]},
                   "descr": {p["name"]: p["title"] for p in ORG["people"] if p["tier"] == "none"}},
        "hierarchy": notice,
        "noise": {"proposal": CH["proposal"], "hearsay": CH["hearsay"], "question": CH["question"],
                  "other_team": CH["other_org"], "stale_echo": CH["stale_echo"],
                  "praise": CH["praise"], "rescind": CH["rescind_own"],
                  "near_miss": CH["near_miss_decision"]},
        "suggest": CH["suggest"],
        "numeric": NUMERIC_MEETINGS,
        "cert": CERT_MEETINGS,
        "derived": DERIVED_MEETINGS,
        "conj": CONJ_MEETINGS,
        "surface": {
            "layout": "sectioned",
            "session_titles": [m["title"] + "  ({date})" for m in SC["meeting_types"]],
            "header_lines": SC["header_lines"],
            "sections": {k: SC["section_headers"][k] for k in ("discussion", "decisions", "actions")},
            "notice_frame": ["### Tooling Governance: how decisions are made (wiki page, pinned)",
                             "(End of wiki page. Meeting minutes follow.)"],
            "artifacts": SC["ai_artifacts"],
            "action_items": clean(FI["action_items"], "action_items", dropped),
            "blocks": [b for b in clean(FI["agenda_items"], "blocks", dropped) if 3 <= b.count("\n") + 1 <= 6],
            "you_prefix": "you",
        },
        "pad": {"first_names": P.FIRST, "last_names": P.LAST, "slots": slots, "families": fams,
                "side": clean(P.SIDE, "pad.side", dropped), "actions": [t if "{p}" in t else t.replace("{t} to", "{p} from {t} to", 1)
                            for t in clean(P.ACTIONS, "pad.actions", dropped)]},
    }
    out = os.path.join(HERE, "revoke", "domains", "corpora", "meetings.json")
    json.dump(c, open(out, "w"), indent=1, ensure_ascii=False)
    print(f"wrote {out}; dropped {len(dropped)} register-bearing filler lines:")
    for w, t in dropped:
        print(f"  {w:<16} {t}")


if __name__ == "__main__":
    main()
