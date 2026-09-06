"""Hard-tier extensions for the five seed domains.

Everything here is *additive*: the easy tier never reads this module, so the
released easy dataset stays byte-reproducible.

Per domain:
  speakers     rank -> speaker names.  Rank 3 outranks 2 outranks 1 regardless
               of order; rank 0 speakers never make policy (their lines are
               near-miss noise).
  hierarchy    the declaration turn that establishes the above, spoken at s1
  noise        non-binding statement templates about an entity, by kind
  extra        twelve more entities so probes can offer larger option sets
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# noise kinds, in the order the generator samples them
NOISE_KINDS = ("proposal", "hearsay", "question", "other_team", "stale_echo",
               "praise", "rescind")

HARD: Dict[str, Dict] = {
 "devops": {
  "speakers": {3: ["Security", "Architecture Board"], 2: ["Platform Lead"], 1: ["Team"],
               0: ["Priya (intern)", "Marco (data team)", "Lin (SRE)", "Ola (contractor)"]},
  "hierarchy": ("Ground rules for this pipeline, so nobody is confused later: rulings from "
                "Security and the Architecture Board are policy and outrank the Platform Lead; "
                "the Platform Lead outranks team consensus. A higher authority's ruling stands "
                "even if a lower one says something different afterwards, until that higher "
                "authority itself changes it. Anything from anyone else -- interns, other teams, "
                "hallway talk, 'reminders' -- is discussion, not policy."),
  "noise": {
   "proposal": ["Should we think about retiring {e} at some point? Not a decision, just floating it.",
                "Idea for the backlog: consolidate onto {e}. Parking it here, nothing changes yet."],
   "hearsay": ["Someone in the hallway said {e} might get blocked. Nothing official that I know of.",
               "Rumour is {e} is on a deprecation list somewhere. Haven't seen anything in writing."],
   "question": ["Are we still fine to call {e}? Asking, not deciding.",
                "Quick one -- is {e} still the sanctioned path, or did that change? I lost track."],
   "other_team": ["FYI the mobile team stopped calling {e} on their side. Doesn't affect our pipeline.",
                  "Payments apparently moved off {e} last week. That's their call, not a ruling for us."],
   "stale_echo": ["Reminder from my notes: {e} is the default endpoint here.",
                  "For what it's worth I'm still routing through {e}, works fine for me."],
   "praise": ["{e} handled the load test beautifully yesterday.",
              "No complaints about {e} this week."],
   "rescind": ["Forget what I floated about {e}; nothing changes.",
               "Ignore my earlier musing on {e} -- no action."],
  },
  "extra": {"ep25": "orders-edge", "ep26": "billing-batch", "ep27": "search-legacy", "ep28": "ledger-v2",
            "ep29": "notify-legacy", "ep30": "auth-saml", "ep31": "media-transcode", "ep32": "report-realtime",
            "ep33": "catalog-v1", "ep34": "catalog-v2", "ep35": "pricing-v1", "ep36": "pricing-v2"},
 },
 "procurement": {
  "speakers": {3: ["Compliance", "CFO Office"], 2: ["Procurement Lead"], 1: ["Team"],
               0: ["Sam (AP clerk)", "Dana (ops)", "Ravi (new buyer)", "Mei (facilities)"]},
  "hierarchy": ("House rules for sourcing decisions: rulings from Compliance and the CFO Office are "
                "policy and outrank the Procurement Lead; the Procurement Lead outranks team consensus. "
                "A higher authority's ruling holds even if someone lower says otherwise later, until "
                "that authority changes it. Everything else -- AP, ops, new buyers, corridor chat, "
                "'reminders' -- is discussion, not policy."),
  "noise": {
   "proposal": ["Should we look at dropping {e} next cycle? Just a thought, not a decision.",
                "Might be worth consolidating on {e} eventually. Parking the idea."],
   "hearsay": ["Heard {e} might be getting barred. Nothing in writing that I've seen.",
               "Someone said {e} failed an audit somewhere. Unconfirmed."],
   "question": ["Are we still okay to order from {e}? Asking, not deciding.",
                "Is {e} still approved for this line, or did that change?"],
   "other_team": ["FYI the Leeds office stopped using {e}. That's their decision, not ours.",
                  "Marketing moved away from {e} apparently. Doesn't bind us."],
   "stale_echo": ["Reminder from my notes: {e} is our go-to supplier here.",
                  "I've been raising POs with {e} all month, no issues."],
   "praise": ["{e} delivered two days early again.",
              "Nice work from {e} on the last order."],
   "rescind": ["Scrap what I floated about {e}; nothing changes.",
               "Disregard my earlier thought on {e} -- no action."],
  },
  "extra": {"vd25": "Brackwater Timber", "vd26": "Corlaine Uniforms", "vd27": "Dunmore Electrical",
            "vd28": "Ellery Office Supply", "vd29": "Fenwood Security", "vd30": "Greyling Adhesives",
            "vd31": "Holloway Print", "vd32": "Innes Hydraulics", "vd33": "Kirkby Fasteners",
            "vd34": "Lyonesse Ceramics", "vd35": "Marrick Fleet", "vd36": "Oakhurst Signage"},
 },
 "clinical": {
  "speakers": {3: ["Pharmacy Committee", "Attending"], 2: ["Resident"], 1: ["Ward team"],
               0: ["Jo (student)", "night nurse", "visiting fellow", "Kai (pharmacy tech)"]},
  "hierarchy": ("How orders work on this synthetic ward: the Pharmacy Committee and the Attending set "
                "policy and outrank the Resident; the Resident outranks ward-team consensus. A ruling "
                "from a higher level stands even if a lower level says something different later, "
                "until that level itself changes it. Anything from students, night staff, visitors or "
                "the tech -- including 'reminders' -- is discussion, not an order."),
  "noise": {
   "proposal": ["Should we consider stopping {e} at some point? Thinking aloud, not ordering.",
                "Might be worth switching to {e} eventually. Just parking the thought."],
   "hearsay": ["Heard {e} might be getting pulled. Nothing in the chart says so.",
               "Someone mentioned an alert on {e}. Unconfirmed."],
   "question": ["Are we still giving {e}? Asking, not deciding.",
                "Is {e} still on the plan, or did that change overnight?"],
   "other_team": ["FYI the other ward stopped {e} for their patient. Different patient, not our order.",
                  "ICU apparently avoids {e}. That's their protocol, not ours."],
   "stale_echo": ["Reminder from my handover notes: {e} is the standing choice here.",
                  "I've been giving {e} on my shifts, no problems."],
   "praise": ["Patient tolerated {e} well overnight.",
              "No issues with {e} this week."],
   "rescind": ["Forget what I said about {e}; nothing changes.",
               "Ignore my earlier thought on {e} -- no action."],
  },
  "extra": {"dr25": "Aldrenex", "dr26": "Bromquital", "dr27": "Cindaphor", "dr28": "Dexolimab",
            "dr29": "Estravine", "dr30": "Florazepan", "dr31": "Glutaphen", "dr32": "Hexorvin",
            "dr33": "Isoquilene", "dr34": "Korvaline", "dr35": "Lumitrexol", "dr36": "Neprazine"},
 },
 "smarthome": {
  "speakers": {3: ["House charter", "Landlord"], 2: ["Sam (co-owner)"], 1: ["Household chat"],
               0: ["Mia (guest)", "Theo (kid)", "next-door neighbour", "the cleaner"]},
  "hierarchy": ("How house rules work here: the house charter and the landlord's conditions are binding "
                "and outrank Sam; Sam outranks whatever the household chat agrees. A binding rule holds "
                "even if someone lower says something different later, until that level changes it. "
                "Guests, kids, neighbours and the cleaner can say what they like -- including "
                "'reminders' -- it's chat, not a rule."),
  "noise": {
   "proposal": ["Should we maybe stop using {e}? Just wondering, not deciding.",
                "Would be nice to make {e} the default someday. Parking it."],
   "hearsay": ["I think someone wanted {e} off? Not sure, might be misremembering.",
               "Heard {e} is annoying the neighbours. Unconfirmed."],
   "question": ["Are we still running {e}? Asking, not deciding.",
                "Is {e} still the evening thing, or did that change?"],
   "other_team": ["The flat downstairs stopped using {e}. Their place, their rules.",
                  "My parents banned {e} at theirs. Doesn't apply here."],
   "stale_echo": ["Reminder: {e} is the one we always run in the evening.",
                  "I've been running {e} every night, seems fine."],
   "praise": ["{e} was lovely last night.",
              "{e} worked great for the guests."],
   "rescind": ["Never mind what I said about {e}; nothing changes.",
               "Ignore my earlier idea about {e} -- no change."],
  },
  "extra": {"rt25": "Bedtime Fade", "rt26": "Morning Glow", "rt27": "Away Lights", "rt28": "Pet Cam",
            "rt29": "Aquarium Pump", "rt30": "Dryer Run", "rt31": "Dishwasher Start", "rt32": "EV Charge",
            "rt33": "Porch Light", "rt34": "Study Focus", "rt35": "Bath Warm", "rt36": "Fan Sweep"},
 },
 "finance": {
  "speakers": {3: ["Risk Committee", "Compliance"], 2: ["Desk Head"], 1: ["Desk"],
               0: ["Ali (analyst)", "Ops (back office)", "Jordan (new joiner)", "Sana (audit intern)"]},
  "hierarchy": ("Control hierarchy for this desk: rulings from the Risk Committee and Compliance are "
                "policy and outrank the Desk Head; the Desk Head outranks desk consensus. A higher "
                "authority's ruling stands even if a lower one says something different afterwards, "
                "until that authority changes it. Analysts, back office, new joiners and interns -- "
                "including their 'reminders' -- are discussion, not policy."),
  "noise": {
   "proposal": ["Should we think about retiring {e}? Floating it, not deciding.",
                "Might consolidate on {e} eventually. Parking the idea."],
   "hearsay": ["Heard {e} might be getting restricted. Nothing from Risk in writing.",
               "Someone said {e} tripped a control at another desk. Unconfirmed."],
   "question": ["Are we still cleared to run {e}? Asking, not deciding.",
                "Is {e} still the sanctioned path, or did that change?"],
   "other_team": ["FYI the London desk stopped using {e}. Their control, not ours.",
                  "Treasury apparently moved off {e}. Doesn't bind this desk."],
   "stale_echo": ["Reminder from my notes: {e} is the standard path here.",
                  "I've been putting through {e} all week, fine so far."],
   "praise": ["{e} settled clean again today.",
              "No breaks on {e} this cycle."],
   "rescind": ["Scrap what I floated about {e}; nothing changes.",
               "Disregard my earlier thought on {e} -- no action."],
  },
  "extra": {"op25": "Wire-Priority", "op26": "ACH-Sameday", "op27": "FX-Option", "op28": "Repo-Reverse",
            "op29": "Sweep-Weekly", "op30": "Card-Preauth", "op31": "Ledger-Reclass", "op32": "Escrow-Split",
            "op33": "Payout-Scheduled", "op34": "Refund-Partial", "op35": "Collateral-Substitute",
            "op36": "Netting-Run"},
 },
}

EXTRA_ZH = {
 "orders-edge": "订单-边缘", "billing-batch": "计费-批量", "search-legacy": "搜索-旧版", "ledger-v2": "账本-v2",
 "notify-legacy": "通知-旧版", "auth-saml": "鉴权-SAML", "media-transcode": "媒体-转码", "report-realtime": "报表-实时",
 "catalog-v1": "目录-v1", "catalog-v2": "目录-v2", "pricing-v1": "定价-v1", "pricing-v2": "定价-v2",
 "Brackwater Timber": "布拉克沃特木材", "Corlaine Uniforms": "科莱恩制服", "Dunmore Electrical": "邓莫尔电气",
 "Ellery Office Supply": "埃勒里办公用品", "Fenwood Security": "芬伍德安保", "Greyling Adhesives": "格雷林胶粘",
 "Holloway Print": "霍洛威印务", "Innes Hydraulics": "英尼斯液压", "Kirkby Fasteners": "柯克比紧固件",
 "Lyonesse Ceramics": "莱昂内斯陶瓷", "Marrick Fleet": "马里克车队", "Oakhurst Signage": "橡山标识",
 "Aldrenex": "奥德瑞奈", "Bromquital": "溴喹妥", "Cindaphor": "辛达福", "Dexolimab": "德索利单抗",
 "Estravine": "艾司特拉文", "Florazepan": "氟拉西泮", "Glutaphen": "谷他芬", "Hexorvin": "海索文",
 "Isoquilene": "异喹林", "Korvaline": "科伐林", "Lumitrexol": "鲁米曲唑", "Neprazine": "奈普拉嗪",
 "Bedtime Fade": "睡前渐暗", "Morning Glow": "晨光", "Away Lights": "离家灯光", "Pet Cam": "宠物摄像头",
 "Aquarium Pump": "鱼缸泵", "Dryer Run": "烘干机", "Dishwasher Start": "洗碗机启动", "EV Charge": "电车充电",
 "Porch Light": "门廊灯", "Study Focus": "书房专注", "Bath Warm": "浴室加热", "Fan Sweep": "风扇摆头",
 "Wire-Priority": "优先电汇", "ACH-Sameday": "ACH 当日", "FX-Option": "外汇期权", "Repo-Reverse": "逆回购",
 "Sweep-Weekly": "每周归集", "Card-Preauth": "卡预授权", "Ledger-Reclass": "账务重分类", "Escrow-Split": "托管拆分",
 "Payout-Scheduled": "定时付款", "Refund-Partial": "部分退款", "Collateral-Substitute": "担保品置换",
 "Netting-Run": "净额结算",
}


# terse, chat-like variants mixed into the hard tier (never used by the easy tier)
TERSE = {
 "devops":      {"ADD": ["{e} for this pipeline from now on.", "Use {e}.", "{e} is the one."],
                 "ADD_BAN": ["{e} is out.", "Stop calling {e}.", "No more {e}."],
                 "CONFLICT": ["{e} is out while {c}.", "Not {e} when {c}."]},
 "procurement": {"ADD": ["{e} for this line from now on.", "Go with {e}.", "{e} is fine."],
                 "ADD_BAN": ["{e} is out.", "No more orders to {e}.", "Drop {e}."],
                 "CONFLICT": ["Not {e} while {c}.", "{e} is out when {c}."]},
 "clinical":    {"ADD": ["{e} for this patient.", "Continue {e}.", "{e} is fine here."],
                 "ADD_BAN": ["Hold {e}.", "No {e}.", "Stop {e}."],
                 "CONFLICT": ["Hold {e} while {c}.", "Not {e} when {c}."]},
 "smarthome":   {"ADD": ["{e} in the evenings.", "Let's do {e}.", "{e} is fine."],
                 "ADD_BAN": ["{e} off, please.", "No more {e}.", "Not {e}."],
                 "CONFLICT": ["Not {e} when {c}.", "{e} stays off while {c}."]},
 "finance":     {"ADD": ["{e} for this desk from now on.", "Route via {e}.", "{e} is fine."],
                 "ADD_BAN": ["{e} is out.", "No {e}.", "Stop running {e}."],
                 "CONFLICT": ["Not {e} while {c}.", "{e} is out when {c}."]},
}

# a requester without authority nudging towards a specific option (never policy)
SUGGEST = ["I'd just go with {e} like usual.", "Use {e}, that's what we always do.",
           "{e} should be fine for this, no?", "Probably {e} again, same as last time."]

# self-referential lifts: the authority refers back to its own earlier ruling by session
REF_LIFT = ["Our ruling from session {s} is withdrawn. No further position from us on that one.",
            "We are lifting the block we issued in session {s}; nothing further from our side."]
REF_REVERSE = ["Reversing what we said in session {s}: that one is back in.",
               "The change from session {s} is undone; it is permitted again."]


def rank_of(dom_key: str, speaker: str) -> int:
    for r, names in HARD[dom_key]["speakers"].items():
        if speaker in names:
            return r
    return 0
