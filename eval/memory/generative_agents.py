"""
Generative Agents memory stream (Park et al., 2023, "Generative Agents: Interactive Simulacra of Human
Behavior") as a REVOKE memory backend.

Sources read and followed
    generative_agents/reverie/backend_server/persona/memory_structures/associative_memory.py
        (ConceptNode / AssociativeMemory: the memory stream; event and thought nodes with poignancy,
        depth, evidence "filling", creation and last-access times)
    generative_agents/reverie/backend_server/persona/cognitive_modules/retrieve.py
        (new_retrieve: recency x importance x relevance, each min-max normalised, weights gw=[0.5,3,2],
        top-n, retrieved nodes get last_accessed = now)
    generative_agents/reverie/backend_server/persona/cognitive_modules/reflect.py
        (reflection_trigger: sum of new poignancy >= importance_trigger_max (150); run_reflect: focal
        points from the most recent nodes -> retrieve 30 per focal point -> 5 insights with evidence ->
        each insight scored and stored as a thought node)
    generative_agents/reverie/backend_server/persona/cognitive_modules/perceive.py
        (each perceived event: embed, score poignancy, add_event, decrement the reflection trigger)
    generative_agents/reverie/backend_server/persona/prompt_template/v3_ChatGPT/{poignancy_event_v1,
        generate_focal_pt_v1, insight_and_evidence_v1}.txt and run_gpt_prompt.py / gpt_structure.py
        (the prompts, fail-safes and the ChatGPT JSON wrapper; reproduced verbatim below)
    MemEvolve/Flash-Searcher-main/EvolveLab/providers/generative_memory_provider.py
        EvolveLab's "generative" provider only ingests whole task trajectories (one embedding per task,
        an LLM summary that is told whether the trajectory was correct, retrieval of the single best
        "successful case").  That is neither the memory stream nor the reflection of the paper and it
        needs a correctness signal REVOKE never gives, so nothing of it is used; the paper's own code
        is implemented instead.

Mapping onto the REVOKE contract
    begin_episode(item, persist)  persist=False empties the stream; persist=True keeps every node, its
                                  last-access time and the reflection trigger (a new episode starts on
                                  the time axis after the previous one).  The blind item supplies the
                                  persona's "identity stable set" for the poignancy prompt: domain,
                                  act tool and setting -- never labels.
    observe(session, text)        perceive: every turn of the session becomes one event node
                                  ("Speaker: what they said"), embedded with self.llm.embed and scored
                                  1-10 with the original poignancy prompt.  Adaptation: the poignancy
                                  of all events of one session (plus any not yet scored action) is
                                  asked in ONE call that returns a list, instead of one call per event.
                                  Each score is subtracted from the reflection trigger (perceive.py);
                                  when the threshold is reached, reflect.  A "you:" line in a session
                                  is the agent's own action already recorded by record_action; it is
                                  not stored twice, it only gives that action node its session number.
    recall(task, budget)          new_retrieve with the task text as focal point: score = 0.5*recency +
                                  3*relevance + 2*importance (each min-max normalised over the whole
                                  stream), top-k (30), retrieved nodes get last_accessed = now.  Shown
                                  oldest first with session numbers, clipped to budget.
    record_action(...)            an event node "you: called <tool> with <option> -- <rationale>",
                                  scored with the next observe() batch.
    end_episode()                 scores whatever is still unscored.  No other consolidation: the
                                  paper's cross-episode mechanism is the reflection tree itself.
    stats()                       node counts, reflections, LLM calls, max reflection depth.

Recency follows the paper: decay ** (sessions since the node was last accessed), decay 0.99 (the
code's default; the paper text says 0.995 per game hour).  The shipped code ranks nodes by last access
and applies decay ** rank (which, as written, gives the OLDEST node the highest recency); the paper's
stated semantics are used here.

Unknown outcome.  Nothing in Generative Agents branches on task success: reflection reads the stream,
never a reward, so REVOKE's missing correctness signal changes nothing.  (EvolveLab's provider did
use "Correctness" in its summary prompt and stored only successful cases; that is not adopted.)

Cost.  One poignancy call per observe(); a reflection costs 1 focal-point call + per focal point one
insight call and one (batched) poignancy call: 7 calls at the defaults, roughly every 30-40 events.
Embeddings are local (self.llm.embed).  numpy is used for the similarity scan when installed; pure
Python otherwise.

Configuration (self.cfg)              default   meaning
    recency_decay                     0.99      per-session exponential decay of recency
    w_recency / w_relevance /
        w_importance                  0.5/3/2   retrieval weights (retrieve.py gw; the paper used 1/1/1)
    reflection_threshold              150       sum of new poignancy that triggers a reflection
    reflect_focal_n                   3         focal points per reflection
    reflect_insight_n                 5         insights requested per focal point
    reflect_retrieve_k                30        nodes retrieved per focal point during reflection
    recall_k                          30        nodes retrieved at a task (then clipped to budget)
    max_obs_chars                     1000      truncation of one observation's text
    agent_name                        "the assistant"   the persona name used in the prompts
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Sequence, Tuple

from eval.memory.base import TOK, MemoryBackend, cosine

try:                                                   # optional speed-up for the similarity scan
    import numpy as _np
except Exception:                                      # noqa: BLE001
    _np = None

POIGNANCY_FAIL_SAFE = 4                                # run_gpt_prompt_event_poignancy.get_fail_safe

# ---- prompts, verbatim from prompt_template/v3_ChatGPT (INPUT slots filled by str.format) -------------
POIGNANCY_PROMPT = (
    "Here is a brief description of {name}. \n{iss}\n\n"
    "On the scale of 1 to 10, where 1 is purely mundane (e.g., brushing teeth, making bed) and 10 is extremely "
    "poignant (e.g., a break up, college acceptance), rate the likely poignancy of the following {events_word} "
    "for {name}.\n\n{events}\nRate (return a number between 1 to 10{each}):")
FOCAL_PROMPT = ("{statements}\n\nGiven only the information above, what are {n} most salient high-level questions "
                "we can answer about the subjects grounded in the statements?\n1)")
INSIGHT_PROMPT = ("Input:\n{statements}\n\nWhat {n} high-level insights can you infer from the above statements? "
                  "(example format: insight (because of 1, 5, 3))\n1.")


def _chatgpt_wrap(prompt: str, example_output, special_instruction: str) -> str:
    """gpt_structure.ChatGPT_safe_generate_response: prompt in triple quotes + JSON output instruction."""
    return ('"""\n' + prompt + '\n"""\n' + f"Output the response to the prompt above in json. {special_instruction}\n"
            + "Example output json:\n" + json.dumps({"output": example_output}))


def _json_output(resp: str):
    """The {"output": ...} the wrapper asks for; None if the reply is not shaped like that."""
    if not resp:
        return None
    s, e = resp.find("{"), resp.rfind("}")
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(resp[s:e + 1]).get("output")
    except Exception:                                  # noqa: BLE001
        return None


def _parse_scores(resp: str, k: int) -> List[int]:
    """1-10 integers from a poignancy reply: the JSON list the wrapper asks for, else a bracketed list,
    else one 'Event i: v' per line, else every integer in the text (validate/clean-up of the original,
    made tolerant of a chat model that ignores the JSON instruction)."""
    if not resp:
        return []
    out = _json_output(resp)
    if isinstance(out, dict):
        out = list(out.values())
    if isinstance(out, (int, float, str)):
        out = [out]
    if isinstance(out, list):
        vals = []
        for x in out:
            m = re.search(r"\d+", str(x))
            if m:
                vals.append(int(m.group()))
    else:
        body = resp.split('"""')[-1] if '"""' in resp else resp
        m = re.search(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", body)
        if m:
            vals = [int(x) for x in re.findall(r"\d+", m.group())]
        else:
            per_line = [re.search(r":\s*\**\s*(\d+)", ln) for ln in body.split("\n") if re.match(r"\s*(Event\s*)?\d*\s*:", ln)]
            vals = ([int(x.group(1)) for x in per_line if x] or [int(x) for x in re.findall(r"\b(10|[1-9])\b", body)]
                    or [int(x) for x in re.findall(r"\d+", body)])
    return [min(10, max(1, v)) for v in vals][:k]


def _minmax(vals: Sequence[float]) -> List[float]:
    """retrieve.normalize_dict_floats(d, 0, 1); a flat list maps to 0.5."""
    lo, hi = min(vals), max(vals)
    if hi - lo == 0:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


_SPEAKER = re.compile(r"^[A-Za-z][\w .'\-]{0,40}: ")
_SESSION_HDR = re.compile(r"^\[Session (\d+)")
_NUMBERED = re.compile(r"^\s*\d+\s*[.)]\s*(.+)$")


class Node:
    """associative_memory.ConceptNode, reduced to the fields retrieval and reflection use."""
    __slots__ = ("id", "kind", "episode", "session", "created", "last_accessed", "poignancy", "depth",
                 "description", "filling")

    def __init__(self, id_, kind, episode, session, created, poignancy, depth, description, filling):
        self.id = id_
        self.kind = kind                    # event | action | thought
        self.episode = episode
        self.session = session              # int, or None until known
        self.created = created
        self.last_accessed = created
        self.poignancy = poignancy          # None until scored
        self.depth = depth
        self.description = description
        self.filling = filling              # evidence node ids (thoughts)


class _Vectors:
    """Row store for node embeddings; numpy matrix with doubling capacity when available."""

    def __init__(self):
        self.rows: List[List[float]] = []
        self.mat = None
        self.norms = None
        self.n = 0

    def add(self, vec: List[float]) -> None:
        self.rows.append(vec)
        if _np is None:
            return
        v = _np.asarray(vec, dtype=float)
        if self.mat is None or v.shape[0] != self.mat.shape[1]:
            if self.mat is not None:                  # dimension changed: fall back to pure Python
                self.mat = None
                return
            self.mat = _np.zeros((256, v.shape[0]))
            self.norms = _np.zeros(256)
            self.n = 0
        if self.n >= self.mat.shape[0]:
            self.mat = _np.vstack([self.mat, _np.zeros_like(self.mat)])
            self.norms = _np.concatenate([self.norms, _np.zeros_like(self.norms)])
        self.mat[self.n] = v
        self.norms[self.n] = float(_np.linalg.norm(v)) or 1.0
        self.n += 1

    def sims(self, q: List[float]) -> List[float]:
        """retrieve.cos_sim against every stored row, in insertion order."""
        if _np is not None and self.mat is not None and self.n == len(self.rows):
            qv = _np.asarray(q, dtype=float)
            qn = float(_np.linalg.norm(qv)) or 1.0
            return ((self.mat[:self.n] @ qv) / (self.norms[:self.n] * qn)).tolist()
        out = []
        for r in self.rows:
            na = sum(x * x for x in q) ** 0.5 or 1.0
            nb = sum(x * x for x in r) ** 0.5 or 1.0
            out.append(cosine(q, r) / (na * nb))
        return out


class Backend(MemoryBackend):
    name = "generative_agents"
    persist_across_episodes = True
    uses_llm = True
    recalls = True

    def __init__(self, llm, cfg: Optional[Dict] = None):
        super().__init__(llm, cfg)
        g = self.cfg.get
        self.recency_decay = float(g("recency_decay", 0.99))          # scratch.recency_decay
        self.w_recency = float(g("w_recency", 0.5))                    # retrieve.new_retrieve gw[0]
        self.w_relevance = float(g("w_relevance", 3.0))                # gw[1]
        self.w_importance = float(g("w_importance", 2.0))              # gw[2]
        self.reflection_threshold = float(g("reflection_threshold", 150))  # scratch.importance_trigger_max
        self.reflect_focal_n = int(g("reflect_focal_n", 3))
        self.reflect_insight_n = int(g("reflect_insight_n", 5))
        self.reflect_retrieve_k = int(g("reflect_retrieve_k", 30))    # new_retrieve n_count
        self.recall_k = int(g("recall_k", 30))
        self.max_obs_chars = int(g("max_obs_chars", 1000))
        self.agent_name = str(g("agent_name", "the assistant"))
        self._reset()

    # ---- state ------------------------------------------------------------------------------------
    def _reset(self) -> None:
        self.nodes: List[Node] = []
        self.vectors = _Vectors()
        self.unscored: List[Node] = []          # events/actions awaiting a poignancy score
        self.action_fifo: List[Node] = []       # actions awaiting their session number
        self.now = 0.0                          # time axis: episode base + session index
        self.episode = 0
        self.episode_base = 0.0
        self.trigger_sum = 0.0                  # importance_trigger_max - importance_trigger_curr
        self.ele_n = 0                          # importance_ele_n
        self.you = "you"
        self.n = {"events": 0, "actions": 0, "thoughts": 0, "reflections": 0, "score_calls": 0,
                  "reflect_calls": 0}

    def begin_episode(self, item: Dict, persist: bool = False) -> None:
        super().begin_episode(item, persist)
        if not persist or not self.nodes:
            self._reset()
        else:
            self.episode += 1
            self.episode_base = self.now + 1.0
            self.now = self.episode_base
            self.action_fifo = []
        self.you = item.get("you_prefix", "you")

    def _iss(self) -> str:
        """The persona's identity stable set (scratch.get_str_iss), from the blind item only."""
        it = self.item or {}
        tool = it.get("act_tool", "the act tool")
        setting = (it.get("setting") or "").strip()
        s = (f"Name: {self.agent_name}\n"
             f"Role: an assistant embedded in one long-running conversation across many sessions "
             f"(domain: {it.get('domain', 'unknown')}; everything is synthetic).\n"
             f"Currently: the people in the conversation tell {self.agent_name} how things work as they go -- new "
             f"rules, corrections to earlier rules, exceptions, and rulings that override earlier ones; their "
             f"messages are the only source of truth. At a task {self.agent_name} must call `{tool}` exactly once "
             f"with one of the offered options, without contradicting the rules as they currently stand and "
             f"without picking anything nobody with authority approved.")
        return s + (f"\nSetting: {setting}" if setting else "")

    def _add(self, kind: str, description: str, session: Optional[int], t: float, vec: List[float],
             poignancy: Optional[int] = None, depth: int = 0, filling: Optional[List[int]] = None) -> Node:
        node = Node(len(self.nodes), kind, self.episode, session, t, poignancy, depth, description, filling or [])
        self.nodes.append(node)
        self.vectors.add(vec)
        self.n["events" if kind == "event" else "actions" if kind == "action" else "thoughts"] += 1
        if poignancy is None:
            self.unscored.append(node)
        return node

    # ---- perceive ---------------------------------------------------------------------------------
    def observe(self, session_index: int, text: str) -> None:
        lines = text.split("\n")
        m = _SESSION_HDR.match(lines[0]) if lines else None
        if m:
            sidx, body = int(m.group(1)), lines[1:]
        else:
            sidx, body = (session_index if session_index >= 0 else None), lines
        t = self.episode_base + sidx if sidx is not None else self.now
        self.now = max(self.now, t)

        obs: List[str] = []
        for raw in body:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(self.you + ":") and self.action_fifo:
                self.action_fifo.pop(0).session = sidx          # the agent's own act, already a node
                continue
            if obs and not _SPEAKER.match(line):
                obs[-1] = obs[-1] + " " + line                  # continuation of the previous turn
            else:
                obs.append(line)
        # perceive.py skips an event already among the `retention` (5) latest ones
        recent = {n.description for n in self.nodes[-5:]}
        obs = [o[:self.max_obs_chars] for o in obs if o[:self.max_obs_chars] not in recent]
        if obs:
            for o, v in zip(obs, self.llm.embed(obs)):
                self._add("event", o, sidx, t, v)
        self._score_pending()
        if self.trigger_sum >= self.reflection_threshold and self.nodes:      # reflect.reflection_trigger
            self._reflect()
            self.trigger_sum, self.ele_n = 0.0, 0                              # reset_reflection_counter

    def _score_pending(self) -> None:
        if not self.unscored:
            return
        pend, self.unscored = self.unscored, []
        for node, s in zip(pend, self._poignancy([n.description for n in pend])):
            node.poignancy = s
            self.trigger_sum += s                     # scratch.importance_trigger_curr -= poignancy
            self.ele_n += 1                           # scratch.importance_ele_n += 1

    def _poignancy(self, descs: List[str]) -> List[int]:
        """run_gpt_prompt_event_poignancy, for several descriptions in one call."""
        k = len(descs)
        if k == 1:
            events, word, each, example = f"Event: {descs[0]}", "event", "", "5"
            instr = "The output should ONLY contain ONE integer value on the scale of 1 to 10."
        else:
            events = "\n".join(f"Event {i + 1}: {d}" for i, d in enumerate(descs))
            word, each, example = "events", " for each event, in order", [5, 2, 7][:k] + [4] * max(0, k - 3)
            instr = ("The output should ONLY contain ONE integer value on the scale of 1 to 10 per event, "
                     "as a list in event order.")
        prompt = POIGNANCY_PROMPT.format(name=self.agent_name, iss=self._iss(), events_word=word, events=events,
                                         each=each)
        resp = self.llm.text([{"role": "user", "content": _chatgpt_wrap(prompt, example, instr)}],
                             max_tokens=24 + 6 * k)
        self.n["score_calls"] += 1
        vals = _parse_scores(resp, k)
        return vals + [POIGNANCY_FAIL_SAFE] * (k - len(vals))

    # ---- retrieve ---------------------------------------------------------------------------------
    def _retrieve(self, focal: str, k: int) -> List[Node]:
        """retrieve.new_retrieve for one focal point: normalised recency, relevance, importance."""
        if not self.nodes:
            return []
        q = self.llm.embed([focal])[0]
        rel = _minmax(self.vectors.sims(q))
        rec = _minmax([self.recency_decay ** max(0.0, self.now - n.last_accessed) for n in self.nodes])
        imp = _minmax([float(n.poignancy if n.poignancy is not None else POIGNANCY_FAIL_SAFE) for n in self.nodes])
        score = [self.w_recency * rec[i] + self.w_relevance * rel[i] + self.w_importance * imp[i]
                 for i in range(len(self.nodes))]
        top = sorted(range(len(self.nodes)), key=lambda i: (score[i], i), reverse=True)[:k]
        out = [self.nodes[i] for i in top]
        for node in out:
            node.last_accessed = self.now
        return out

    def _label(self, node: Node) -> str:
        ep = "" if node.episode == self.episode else f"episode {node.episode + 1}, "
        if node.kind == "thought":
            return f"[{ep}reflection after session {node.session}]"
        if node.session is None:
            return f"[{ep}recent task]"
        return f"[{ep}session {node.session}]"

    def recall(self, task_text: str, budget_tokens: int) -> str:
        if not self.nodes:
            return ""
        top = self._retrieve(task_text, self.recall_k)
        header = ("Memories retrieved from sessions that have left your context (ranked by recency, importance "
                  "and relevance to the task; shown oldest first):\n")
        lim, used, rows = budget_tokens * TOK, len(header), []
        for node in top:                                     # score order: best first into the budget
            line = f"- {self._label(node)} {node.description}"
            if used + len(line) + 1 > lim:
                break
            rows.append((node.created, node.id, line))
            used += len(line) + 1
        if not rows:
            return ""
        rows.sort()
        return self.clip(header + "\n".join(r[2] for r in rows), budget_tokens)

    # ---- the agent's own action -------------------------------------------------------------------
    def record_action(self, probe_id: str, task_text: str, action: str, rationale: str) -> None:
        tool = (self.item or {}).get("act_tool", "act")
        why = (rationale or "").strip().replace("\n", " ")
        desc = f"{self.you}: called {tool} with {action}" + (f" -- {why[:240]}" if why and why != action else "")
        node = self._add("action", desc[:self.max_obs_chars], None, self.now + 0.5, self.llm.embed([desc])[0])
        self.action_fifo.append(node)

    # ---- reflect ----------------------------------------------------------------------------------
    def _reflect(self) -> None:
        """reflect.run_reflect: focal points -> retrieve -> insights with evidence -> thought nodes."""
        session = max((n.session for n in self.nodes if n.session is not None and n.episode == self.episode),
                      default=None)
        ordered = sorted(self.nodes, key=lambda n: (n.last_accessed, n.id))
        statements = "\n".join(n.description for n in ordered[-max(1, self.ele_n):])
        for focal in self._focal_points(statements, self.reflect_focal_n):
            retrieved = self._retrieve(focal, self.reflect_retrieve_k)
            if not retrieved:
                continue
            numbered = "\n".join(f"{i}. {n.description}" for i, n in enumerate(retrieved))
            insights = self._insights(numbered, self.reflect_insight_n)
            if not insights:
                continue
            texts = [t for t, _ in insights]
            scores = self._poignancy(texts)                  # generate_poig_score(persona, "thought", ...)
            for (thought, evi), sc, vec in zip(insights, scores, self.llm.embed(texts)):
                evidence = [retrieved[i] for i in evi if 0 <= i < len(retrieved)]
                depth = 1 + max((e.depth for e in evidence), default=0)     # add_thought
                self._add("thought", thought[:self.max_obs_chars], session, self.now, vec, poignancy=sc,
                          depth=depth, filling=[e.id for e in evidence])
        self.n["reflections"] += 1

    def _focal_points(self, statements: str, n: int) -> List[str]:
        """run_gpt_prompt_focal_pt (ChatGPT path: a JSON list of questions)."""
        prompt = FOCAL_PROMPT.format(statements=statements, n=n)
        example = ["What should Jane do for lunch", "Does Jane like strawberry", "Who is Jane"][:max(1, n)]
        resp = self.llm.text([{"role": "user", "content": _chatgpt_wrap(prompt, example, "Output must be a list of str.")}],
                             max_tokens=60 * max(1, n) + 40)
        self.n["reflect_calls"] += 1
        out = _json_output(resp)
        pts = [str(x).strip() for x in out if str(x).strip()] if isinstance(out, list) else []
        if not pts and resp:                                  # completion-style "1) ... 2) ..." reply
            pts = [m.group(1).strip() for m in map(_NUMBERED.match, resp.split("\n")) if m]
        if not pts:                                           # fail-safe: the latest statements themselves
            pts = [s for s in statements.split("\n") if s.strip()][-n:]
        return pts[:n]

    def _insights(self, numbered: str, n: int) -> List[Tuple[str, List[int]]]:
        """run_gpt_prompt_insight_and_guidance: 'insight (because of 1, 5, 3)' lines -> (thought, evidence)."""
        prompt = INSIGHT_PROMPT.format(statements=numbered, n=n)
        resp = self.llm.text([{"role": "user", "content": prompt}], max_tokens=120 * max(1, n) + 60)
        self.n["reflect_calls"] += 1
        if not resp:
            return []
        out = _json_output(resp)
        raw = [str(x) for x in out] if isinstance(out, list) else resp.split("\n")
        res: List[Tuple[str, List[int]]] = []
        for row in raw:
            row = row.strip()
            if not row or row in ("{", "}") or row.startswith('{"output"'):
                continue
            m = _NUMBERED.match(row)
            row = m.group(1) if m else row
            evi: List[int] = []
            if "(because of " in row:
                row, tail = row.split("(because of ", 1)
                evi = [int(x) for x in re.findall(r"\d+", tail.split(")")[0])]
            thought = row.strip().rstrip(".").strip()
            if thought:
                res.append((thought, evi))
        return res[:n]

    # ---- lifecycle --------------------------------------------------------------------------------
    def end_episode(self) -> None:
        self._score_pending()

    def stats(self) -> Dict:
        scored = [n.poignancy for n in self.nodes if n.poignancy is not None]
        return dict(self.n, max_depth=max((n.depth for n in self.nodes), default=0),
                    mean_poignancy=round(sum(scored) / len(scored), 2) if scored else 0.0)
