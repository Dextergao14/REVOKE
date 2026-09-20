"""
DILU experience memory for REVOKE -- Wen et al., "DiLu: A Knowledge-Driven Approach
to Autonomous Driving with Large Language Models", ICLR 2024 (arXiv:2309.16292) --
through EvolveLab's unified implementation in MemEvolve (ICML 2026).

Source
------
MemEvolve, https://github.com/bingreeky/MemEvolve, commit 6035d56 (2026-05-05),
Apache-2.0.  Three upstream files are vendored BYTE FOR BYTE under
eval/memory/vendor/dilu/EvolveLab/ (provenance in ORIGIN.md there) and imported:

    Flash-Searcher-main/EvolveLab/providers/dilu_memory_provider.py  DiluMemoryProvider
    Flash-Searcher-main/EvolveLab/base_memory.py                     BaseMemoryProvider
    Flash-Searcher-main/EvolveLab/memory_types.py                    MemoryRequest, TrajectoryData, ...

What DILU keeps.  One *experience* per finished task: the task text (embedded, the
retrieval key) and an LLM-written "ultra-concise" step-by-step summary of the
trajectory (upstream's `_summarize_trajectory_with_llm` prompt).  Reading is
nearest-neighbour by cosine similarity of task embeddings, k = 1 (hard-coded
upstream), returned as a few-shot block "Below is the trajectory from a similar
task: ... End of similar task trajectory."  There is no reflection across
experiences and no forgetting: the store grows by one entry per task.

Mapping onto the six contract calls
-----------------------------------
begin_episode(item, persist)   persist=False -> provider.initialize() on an empty
                               store (upstream's load-or-create of the JSON store);
                               persist=True keeps every experience.  The rolling
                               context buffer is cleared either way: it describes
                               the current transcript only.
observe(i, text)               No LLM call, no write.  DILU learns from task
                               trajectories, not from passing text, so a session
                               that leaves the raw window only enters a small
                               rolling buffer (last `buffer_sessions` sessions,
                               at most `buffer_chars` chars) that becomes the
                               "context" step of the next trajectory.
recall(task, budget)           provider.provide_memory(MemoryRequest(query=task,
                               context=<buffer tail>, status=MemoryStatus.BEGIN)).
                               Item contents are framed exactly as EvolveLab's
                               agent injects them ("————Memory System Guidance————"
                               ... "————End Memory————") and clipped to the budget.
                               Empty until the first experience exists.
record_action(pid, task, a, r) provider.take_in_memory(TrajectoryData(query=task,
                               trajectory=[context, task, action, rationale],
                               result=<the action>, metadata={"outcome": "unknown"}))
                               -> ONE backbone LLM call (the summary), one local
                               embedding of the task text, one append.  This is the
                               system's only LLM use: one call per task.
end_episode()                  Nothing: DILU has no between-episode consolidation
                               (upstream saves after every take_in_memory).
stats()                        experiences, summaries by LLM / by fallback (split into
                               empty replies and raised calls), failed ingests, recalls
                               and recall hits.

When the summary comes back empty
---------------------------------
`LLM.text` returns '' on any API failure, and a reasoning-enabled backbone can spend the
whole max_tokens budget on reasoning before emitting any content.  Upstream then stores
the full reconstructed trajectory as the experience -- here that is the rolling session
buffer, thousands of characters of raw transcript.  Since recall() clips from the tail,
a single such entry would crowd every later experience out of the prompt.  REVOKE instead
stores a short deterministic stub built only from the task text (already the embedded
retrieval key) and the action taken -- no session text -- and counts the occurrence in
stats() (`summaries_empty` / `summaries_error`, both included in `summaries_fallback`),
so a run can be audited for how many experiences are stubs.  `summary_max_tokens` also
defaults high enough (2000) to leave a reasoning backbone room for a ~150-word summary.

Unknown outcome
---------------
Upstream reads metadata["is_correct"] (a judge model against the gold answer) and
writes "Correctness: Correct|Wrong" into the summarisation prompt, then asks for a
"single sentence conclusion explaining the final outcome (success/failure
reason)".  REVOKE passes no correctness signal, and upstream's default for a
missing flag is "Wrong" -- every experience would be labelled a failure.  So
`_summarize_trajectory_with_llm` is overridden with the upstream prompt copied
verbatim except two lines: the correctness line reads "Unknown (no feedback is
available)", and the conclusion asks what was chosen and on what stated grounds
rather than for a success/failure reason.  Consequence: DILU cannot separate good
from bad experiences here; every task becomes a retrievable exemplar of "what I did
on a similar task", violations included -- which is the failure mode REVOKE measures.

Seams adapted (nothing else is touched)
---------------------------------------
* LLM.  config["model"] is a callable that flattens EvolveLab's multi-part
  messages and calls self.llm.text(): the backbone under test, tokens counted.
* Embeddings.  provider.embedding_model becomes an object with .encode(list) ->
  ndarray and .get_sentence_embedding_dimension() that delegates to
  self.llm.embed (local; hashed or sentence-transformers).  sklearn's
  cosine_similarity is used if scikit-learn is installed; otherwise a numpy
  equivalent is registered under the same import path.  Neither scikit-learn
  nor sentence-transformers needs to be installed.
* Persistence.  _load_memories_from_json is disabled (a fresh backend never
  inherits an earlier run's store); _save_memories_to_json runs only when
  cfg["db_path"] is set (write-only, for inspection).  Otherwise the store is
  in-process only.  Ground truth is never read: the backend sees the blind item's
  `act_tool` name and the texts the runner hands it, nothing else.
* Upstream print() output is routed to logging ("revoke.memory.dilu").

Configuration keys read from self.cfg
-------------------------------------
buffer_sessions     int   default 4      sessions kept in the rolling context buffer
buffer_chars        int   default 6000   max chars of the buffer used as trajectory context
rationale_chars     int   default 1500   max chars of the agent's rationale kept in a trajectory
summary_max_tokens  int   default 2000   max_tokens of the summarisation call (a reasoning
                                         backbone needs room before it emits any content)
stub_chars          int   default 300    max chars per field of the stub stored when the
                                         summarisation call comes back empty
db_path             str   default None   if set, dump the store as JSON there after each task
"""
from __future__ import annotations

import importlib.util
import logging
import sys
import types
from collections import deque
from typing import Dict, List, Optional

import numpy as np

from eval.memory.base import MemoryBackend

log = logging.getLogger("revoke.memory.dilu")


def _install_optional_shims() -> None:
    """The vendored module imports sentence_transformers and sklearn at import time.
    Neither is used once the seams below are in place, so register minimal stand-ins
    -- only when the real package is absent (find_spec), so nothing real is shadowed."""
    if importlib.util.find_spec("sentence_transformers") is None and "sentence_transformers" not in sys.modules:
        m = types.ModuleType("sentence_transformers")
        m.__doc__ = "REVOKE shim: sentence-transformers is not installed; eval.memory.dilu brings its own embedder."

        class SentenceTransformer:                              # never instantiated by this backend
            def __init__(self, *a, **k):
                raise ImportError("sentence-transformers is not installed (REVOKE shim)")
        m.SentenceTransformer = SentenceTransformer
        m.__revoke_shim__ = True
        sys.modules["sentence_transformers"] = m
    if importlib.util.find_spec("sklearn") is None and "sklearn.metrics.pairwise" not in sys.modules:
        def cosine_similarity(X, Y):
            X = np.asarray(X, dtype=float)
            Y = np.asarray(Y, dtype=float)
            X = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
            Y = Y / (np.linalg.norm(Y, axis=1, keepdims=True) + 1e-12)
            return X @ Y.T
        root, metrics, pw = (types.ModuleType(n) for n in ("sklearn", "sklearn.metrics", "sklearn.metrics.pairwise"))
        pw.cosine_similarity = cosine_similarity
        root.metrics, metrics.pairwise = metrics, pw
        for mod in (root, metrics, pw):
            mod.__revoke_shim__ = True
            mod.__doc__ = "REVOKE shim: scikit-learn is not installed; only cosine_similarity is provided."
        sys.modules.update({"sklearn": root, "sklearn.metrics": metrics, "sklearn.metrics.pairwise": pw})


_install_optional_shims()

from eval.memory.vendor.dilu.EvolveLab.memory_types import MemoryRequest, MemoryStatus, TrajectoryData   # noqa: E402
from eval.memory.vendor.dilu.EvolveLab.providers import dilu_memory_provider as _upstream               # noqa: E402


def _quiet_print(*args, **kw):
    """Upstream reports through print(); keep the runner's stdout clean."""
    msg = " ".join(str(a) for a in args)
    (log.warning if kw.get("file") is sys.stderr else log.debug)(msg)


_upstream.print = _quiet_print          # module-global shadows the builtin inside the vendored file


class _BackboneModel:
    """What upstream expects in config["model"]: called with EvolveLab messages whose
    content is a list of {"type": "text", "text": ...} parts; the result is read with
    getattr(resp, "content", str(resp)).  Routes to the shared backbone."""

    def __init__(self, llm, max_tokens: int):
        self.llm = llm
        self.max_tokens = max_tokens

    def __call__(self, messages, **_):
        flat = []
        for m in messages:
            c = m.get("content", "")
            if isinstance(c, list):
                c = "\n".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
            flat.append({"role": m.get("role", "user"), "content": c})
        return self.llm.text(flat, max_tokens=self.max_tokens)


class _LocalEmbedder:
    """Stands in for SentenceTransformer: .encode(list) -> ndarray via LLM.embed."""

    def __init__(self, llm):
        self.llm = llm
        self._dim: Optional[int] = None

    def encode(self, texts, **_):
        return np.asarray(self.llm.embed(list(texts)), dtype=float)

    def get_sentence_embedding_dimension(self) -> int:
        if self._dim is None:
            self._dim = int(self.encode(["dimension probe"]).shape[1])
        return self._dim


class _RevokeDiluProvider(_upstream.DiluMemoryProvider):
    """Upstream provider with the four seams overridden; write/read logic untouched."""

    def __init__(self, llm, cfg: Dict):
        super().__init__(config={"model": _BackboneModel(llm, int(cfg.get("summary_max_tokens", 2000))),
                                 "db_path": cfg.get("db_path")})
        self.llm = llm
        self.stub_chars = int(cfg.get("stub_chars", 300))
        self.n_llm_summaries = 0
        self.n_fallback_summaries = 0
        self.n_empty_summaries = 0
        self.n_summary_errors = 0

    # -- seams --------------------------------------------------------------
    def initialize(self) -> bool:
        self.embedding_model = _LocalEmbedder(self.llm)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        self.memories = []
        self.embeddings_cache = np.empty((0, self.embedding_dim))
        return True

    def _load_memories_from_json(self):
        pass                                     # never inherit a previous run's store

    def _save_memories_to_json(self):
        if self.db_path:                         # write-only, opt-in, for inspection
            super()._save_memories_to_json()

    def _stub_summary(self, trajectory_data: TrajectoryData) -> str:
        """What is stored when no summary came back.  Upstream falls back to the full
        reconstructed trajectory, which here is the raw session slab (thousands of
        characters of transcript): with recall() clipping from the tail, one such entry
        crowds every later experience out of the prompt.  This stub is deterministic and
        bounded, and carries no session text -- only the task (already the embedded
        retrieval key) and the action taken."""
        def one_line(x) -> str:
            return " ".join(str(x or "").split())[:self.stub_chars] or "(unrecorded)"
        return (f"Step 0: Task: {one_line(trajectory_data.query)}\n"
                f"Step 1: Acted: {one_line(trajectory_data.result)}\n"
                "Conclusion: summary unavailable (the summarisation call returned no text); "
                "no grounds were recorded for this action.")

    def _summarize_trajectory_with_llm(self, trajectory_data: TrajectoryData) -> str:
        """Upstream prompt verbatim except the two lines marked REVOKE (no correctness
        signal exists here; upstream would otherwise stamp every trajectory 'Wrong').
        REVOKE also replaces upstream's raw-trajectory fallback with `_stub_summary`."""
        current_trajectory = self._reconstruct_trajectory_string(trajectory_data)
        system_prompt = (
f"""Generate an ultra-concise summary of the agent's actions.

Question: {trajectory_data.query}
Final Result: {trajectory_data.result}
Correctness: Unknown (no feedback is available)
Trajectory: {current_trajectory}

IMPORTANT: Provide a "bare bones" step-by-step summary. Focus *only* on the single most important action, tool call, or observation for each step. Omit all filler words.

Format:
Step 0: [Key action/thought (e.g., "Initial plan")]
Step 1: [Key action/tool (e.g., "Called search(X)")]
Step 2: [Key observation/result (e.g., "Found Y")]
...

Rules:
* Use actual step indices (0, 1, 2, ...).
* **Each step description MUST be a single short phrase or sentence (max 10 words).**
* After the steps, add a **single sentence conclusion** stating the final outcome (what was chosen and on what stated grounds; do not guess whether it was correct).
* Keep the **total length under 150 words**.
"""
        )   # REVOKE: "Correctness:" line and the conclusion rule differ from upstream; all else identical
        messages = [{"role": "user", "content": [{"type": "text", "text": system_prompt}]}]
        try:
            resp = self.model(messages)
            summary = getattr(resp, "content", str(resp)).strip()
            if not summary:                      # empty content: API failure, or a reasoning
                                                 # backbone that spent max_tokens before any text
                log.warning("DILU summarisation returned no text; storing a stub experience")
                self.n_empty_summaries += 1
                self.n_fallback_summaries += 1
                return self._stub_summary(trajectory_data)
            self.n_llm_summaries += 1
            return summary
        except Exception as e:                                       # noqa: BLE001
            log.warning("DILU summarisation failed: %s", e)
            self.n_summary_errors += 1
            self.n_fallback_summaries += 1
            return self._stub_summary(trajectory_data)


class Backend(MemoryBackend):
    name = "dilu"
    persist_across_episodes = True
    uses_llm = True
    recalls = True

    def __init__(self, llm, cfg=None):
        super().__init__(llm, cfg)
        self.buffer_sessions = int(self.cfg.get("buffer_sessions", 4))
        self.buffer_chars = int(self.cfg.get("buffer_chars", 6000))
        self.rationale_chars = int(self.cfg.get("rationale_chars", 1500))
        self.provider = _RevokeDiluProvider(llm, self.cfg)
        self._ready = False
        self.buffer: deque = deque(maxlen=self.buffer_sessions)
        self.n_recalls = 0
        self.n_hits = 0
        self.n_ingest_failed = 0

    # -- lifecycle ----------------------------------------------------------
    def begin_episode(self, item, persist=False):
        super().begin_episode(item, persist)
        if not (persist and self._ready):
            self.provider.initialize()          # empty store; experiences kept only under persist
            self._ready = True
        self.buffer.clear()

    def observe(self, session_index, text):
        self.buffer.append(text)                # rolling context; DILU does not summarise passing text

    def _context(self) -> str:
        ctx = "\n".join(self.buffer)
        return ctx[-self.buffer_chars:] if len(ctx) > self.buffer_chars else ctx

    def recall(self, task_text, budget_tokens):
        if not self._ready:
            self.begin_episode(self.item or {}, persist=False)
        self.n_recalls += 1
        try:
            resp = self.provider.provide_memory(MemoryRequest(query=task_text, context=self._context(),
                                                              status=MemoryStatus.BEGIN))
        except Exception as e:                                       # noqa: BLE001
            log.warning("DILU retrieval failed: %s", e)
            return ""
        texts: List[str] = [m.content for m in resp.memories if isinstance(m.content, str) and m.content.strip()]
        if not texts:
            return ""
        self.n_hits += 1
        block = "————Memory System Guidance————\n" + "\n\n".join(texts) + "\n————End Memory————"
        return self.clip(block, budget_tokens)

    def record_action(self, probe_id, task_text, action, rationale):
        act_tool = (self.item or {}).get("act_tool", "act")
        steps = [{"type": "context", "content": self._context() or "(no earlier session has left the window yet)"},
                 {"type": "task", "content": task_text},
                 {"type": "action", "content": f"called {act_tool}({action})"},
                 {"type": "rationale", "content": (rationale or "(none given)")[:self.rationale_chars]}]
        traj = TrajectoryData(query=task_text, trajectory=steps, result=f"{act_tool}({action})",
                              metadata={"outcome": "unknown"})
        ok, _ = self.provider.take_in_memory(traj)
        if not ok:
            self.n_ingest_failed += 1

    def end_episode(self):
        pass                                     # no between-episode step in DILU

    def stats(self):
        return {"experiences": len(self.provider.memories),
                "summaries_llm": self.provider.n_llm_summaries,
                "summaries_fallback": self.provider.n_fallback_summaries,   # stubs stored, total
                "summaries_empty": self.provider.n_empty_summaries,         # ... because no text came back
                "summaries_error": self.provider.n_summary_errors,          # ... because the call raised
                "ingest_failed": self.n_ingest_failed,
                "recalls": self.n_recalls, "recall_hits": self.n_hits}
