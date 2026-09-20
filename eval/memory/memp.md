# MEMP (procedural memory)

**Source.** Fang et al. 2025, *Memp: Exploring Agent Procedural Memory* (arXiv:2508.06433); the EvolveLab `MempMemoryProvider` from MemEvolve/Flash-Searcher, vendored byte-identical (`eval/memory/vendor/memp_evolvelab/`) and subclassed at four seams (LLM hook, embeddings, initialisation, JSON persistence). Prompts, record format, retrieval and the add/adjust logic are the upstream code.

**What it stores.** One procedural record per task the agent has acted on: the task text, a <100-word high-level *script* abstracted from the trajectory, and a <150-word *concrete-steps summary* of the same trajectory, plus an embedding of the task text. Nothing is stored per session: sessions that leave the raw window are kept only in a rolling buffer (default 3000 tokens) that becomes the observation steps of the next trajectory.

**When it writes.** After every action: the trajectory (buffered sessions -> the agent's rationale -> the act call, with the act call as the trajectory's result) is distilled by two backbone calls into a new record (`_add_new_memory`). Upstream instead *revises* the record it served (`_adjust_memory`) when a trajectory is marked failed; REVOKE passes no correctness signal, so every trajectory takes the add path and the store grows by one record per task, wrong actions distilled like right ones. The upstream summary prompt would print `Correctness: Wrong` when the flag is absent; that one line reads `Unknown` here, the only prompt change.

**How it reads.** At a task, the task text is embedded (local embedder) and the top-1 record by cosine similarity (upstream's fixed `top_k`, configurable) is placed in the prompt as upstream formats it -- `[High-Level Script]` then `[Concrete Steps (Example)]` -- clipped to the recall budget. The ids served are cached by exact query text, as upstream.

**Persistence.** `persist=True` keeps records, embeddings and the served-id cache across the episodes of a world; `persist=False` empties them. No disk I/O unless `store_json` is set (temp dir).

**Adaptation flag.** `adjust_on_repeat` (off by default): if the same task stem recurs in an episode and the agent now picks a different option, the trajectory is fed to upstream's failure branch so `_adjust_memory` rewrites the record that was served, instead of adding one. A proxy for failure, not ground truth -- in REVOKE the licensed option legitimately changes over time -- so it is reported only as a variant.

**Cost.** Two backbone calls per task (script + summary; a third per served record when adjusting), none per session; each call sees the buffered sessions, so cost scales with `buffer_tokens`.
