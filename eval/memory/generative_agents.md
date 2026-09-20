# Generative Agents (Park et al., 2023) -- memory stream with reflection

**Stores.** One memory stream of nodes as in the paper's `AssociativeMemory`: *events* (one per transcript turn,
"Speaker: text", tagged with its session), the agent's own *actions* ("you: called `<tool>` with `<option>` --
rationale"), and *thoughts* (reflections). Each node has a local embedding (`LLM.embed`), an integer poignancy
1-10, creation and last-access times on a session axis and, for thoughts, the ids of its evidence nodes (the
reflection tree; depth = 1 + depth of the evidence).

**Writes.** When a session leaves the raw window each turn becomes exactly one event node -- no line is ever
merged into its predecessor, whether or not it looks like "Speaker: text" (headings and narrative lines are
turns too, and no turn in the long tier contains an internal newline). Poignancy is rated with the original
`poignancy_event_v1` prompt on the backbone under test, one call per session returning a list (the original
rates events one at a time). Scores accumulate on the reflection trigger; at the threshold (150, the code's
`importance_trigger_max`) the agent reflects exactly as `reflect.py` does: 3 focal questions from the most
recently accessed nodes, 30 nodes retrieved per question, 5 insights with evidence per question, each insight
scored and stored as a thought. The action after every task is written as an event node.

**Reads.** The task text is the focal point of `new_retrieve`: recency (0.99 per session since last access),
importance and cosine relevance are each min-max normalised over the stream and combined with the shipped
weights 0.5 / 2 / 3; the top 30 nodes are shown oldest-first with session numbers, their `last_accessed` is
set to now, and the text is clipped to the recall budget.

**Adaptations.** Batched poignancy scoring, with a fixed `[5, 2, 7]` example and the required length stated in
the instruction (the original's example is the single string `"5"`; padding the example out to *k* with the
fail-safe value 4 anchored long sessions onto a constant score). Every memory call gets at least
`poignancy_max_tokens` (600) completion tokens: `base.LLM` defaults to `reasoning="low"` and reasoning tokens
count against `max_tokens`, so the old 30-60 token cap silently returned `''` and made every score the
fail-safe. `stats()` reports `empty_replies` and `score_failsafe` so that failure is visible. Both reflection
prompts truncate each statement to `reflect_stmt_chars` (300). The persona's identity stable set is built from
the blind item (domain, act tool, setting); recency uses the paper's time-since-access semantics rather than
the code's rank-based variant. Prompt sources: `v3_ChatGPT/{poignancy_event_v1, generate_focal_pt_v1}.txt`
with the JSON wrapper, and `v2/insight_and_evidence_v1.txt` un-wrapped (`run_gpt_prompt_insight_and_guidance`
has no ChatGPT branch). No step depends on task success, so REVOKE's missing correctness signal changes
nothing. With `--persist` the stream, access times and trigger carry over across the episodes of a world.

**Cost and requirements.** numpy is required, not optional: the pure-Python similarity fallback is ~1000x
slower (0.10 ms vs 112 ms per scan over 4,000 nodes) and is only viable for the smoke test. Measured on one
full episode with a fake backbone (window 8000, recall budget 4000): clinical_ward 13,527 event nodes, 2,096
memory calls, 7.6M prompt chars (~1.9M tokens); game_narrative 40,883 event nodes, 3,378 calls, 15.7M prompt
chars (~3.9M tokens) and ~360 MB peak RSS. One node per turn raises the reflection count as well as the node
count, so reflection still dominates the bill -- plan the 50-episode long tier from those numbers. Because a
persisted world holds every episode's nodes in one instance (~800k nodes, GB-scale), run `--persist` with
`--workers 1`.
