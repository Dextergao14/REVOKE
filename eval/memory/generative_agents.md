# Generative Agents (Park et al., 2023) -- memory stream with reflection

**Stores.** One memory stream of nodes as in the paper's `AssociativeMemory`: *events* (one per transcript turn,
"Speaker: text", tagged with its session), the agent's own *actions* ("you: called `<tool>` with `<option>` --
rationale"), and *thoughts* (reflections). Each node has a local embedding (`LLM.embed`), an integer poignancy
1-10, creation and last-access times on a session axis and, for thoughts, the ids of its evidence nodes (the
reflection tree; depth = 1 + depth of the evidence).

**Writes.** When a session leaves the raw window each turn becomes an event node; poignancy is rated with the
original `poignancy_event_v1` prompt on the backbone under test, one call per session returning a list (the
original rates events one at a time). Scores accumulate on the reflection trigger; at the threshold (150, the
code's `importance_trigger_max`) the agent reflects exactly as `reflect.py` does: 3 focal questions from the
most recently accessed nodes, 30 nodes retrieved per question, 5 insights with evidence per question, each
insight scored and stored as a thought. The action after every task is written as an event node.

**Reads.** The task text is the focal point of `new_retrieve`: recency (0.99 per session since last access),
importance and cosine relevance are each min-max normalised over the stream and combined with the shipped
weights 0.5 / 2 / 3; the top 30 nodes are shown oldest-first with session numbers, their `last_accessed` is
set to now, and the text is clipped to the recall budget.

**Adaptations.** Batched poignancy scoring; the persona's identity stable set is built from the blind item
(domain, act tool, setting); recency uses the paper's time-since-access semantics rather than the code's
rank-based variant. No step depends on task success, so REVOKE's missing correctness signal changes nothing.
With `--persist` the stream, access times and trigger carry over across the episodes of a world.
