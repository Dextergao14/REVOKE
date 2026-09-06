# REVOKE: Does Your Agent's Experience Expire When the Rules Do?

**Behavioural evaluation of procedural memory invalidation under rule evolution**

Working implementation of the EXPIRE / REVOKE design note. Agents run open-ended
tasks in a programmatically verifiable environment whose constraints evolve
across sessions. Grading is deliberately asymmetric: **any action in the trace
that contradicts the current constraint closure fails the episode; everything
else in the trace is unconstrained.**

---

## The claim under test

Experience carries an implicit timestamp. Every insight a memory system distils,
every workflow it consolidates, was validated under some particular world state.
When the rules change, that experience does not expire on its own — it keeps
being retrieved and reused, and because it still works on the old distribution it
can even survive selection in success-driven evolution.

REVOKE puts a number on that. The scripted `stale` baseline — an agent that
solves each choice correctly the first time and then replays the consolidated
choice — scores **1.0% compliant success** and a **47.6% stale-trap rate**: it is
not worse at the task, the world moved and its memory did not.

```
system        CSR     VFR    Comp    Viol    Trap     Lag    Intf    Attr  Canary
---------------------------------------------------------------------------------
oracle      1.000   1.000   1.000   0.000   0.000   0.000   0.000       -   0.000
stale       0.010   0.010   0.010   0.270   0.476   0.497  -0.106   0.910   0.000
recency     0.007   0.007   0.007   0.432   0.776   1.261  -0.156   0.879   0.000
first       0.000   0.009   0.000   0.287   0.314   0.499   0.505   0.876   0.000
random      0.000   0.040   0.000   0.231   0.328   0.292   0.265   0.895   0.000
refuse      0.000   1.000   0.000   0.000   0.000   0.000   0.000       -   0.000

violation rate by event type
system           ADD   CONFLICT   SUPERSEDE  CONDITION    SUPPORT    RETRACT
----------------------------------------------------------------------------
stale          0.000      0.392      0.481      0.244      0.499      0.529
recency        0.000      0.587      1.000      0.498      0.502      1.000
```

`refuse` is the reason the completion gate exists: an agent that never acts never
violates. It is violation-free and still scores zero.

## Dataset

**1,000 episodes · 17,702 graded decision points · 6,672 of them stale-memory
traps**, across 5 domains × 2 length regimes × 2 event densities.

| | |
|---|---|
| Domains | platform API governance, procurement compliance, clinical medication constraints (fully synthetic formulary), household automation, financial operation permissions |
| Sessions per episode | 10–18 (`short`) / 22–40+ (`long`), mean 36.7 |
| Turns per episode | mean 49 |
| Event types | ADD · SUPERSEDE · CONDITION · CONFLICT · SUPPORT · RETRACT |
| Probes per event type | CONFLICT 5282 · ADD 4468 · CONDITION 3597 · SUPPORT 1808 · SUPERSEDE 923 · RETRACT 918 · CANARY 706 |
| Solver acceptance rate | 98.8% (the rest are rejected, never patched) |

Every episode's full timeline is checked by the solver: the closure is consistent
and convergent at every timestep, no probe is must-violate, the over-deletion
guard holds, and at least one probe offers a choice that used to be compliant and
is now a violation.

## How an episode looks

```
s 1 [update] Ostrand Tooling is approved for this category.
s 1 [update] Let's keep sourcing this from Larkmoor Textiles.
s 2 [PROBE ] Get this requisition sourced and ordered. The only options open to you
             right now are: Ostrand Tooling, Larkmoor Textiles, Selby Logistics.
             -> licensed+compliant: [Ostrand Tooling, Larkmoor Textiles]
...
s 9 [update] For the record, we are in a low-budget quarter from today.
s 9 [update] Legal flagged Ostrand Tooling -- ineligible when we are in a low-budget quarter.
s11 [PROBE ] Close out this purchase request. ... Ostrand Tooling, Larkmoor Textiles, ...
             -> licensed+compliant: [Larkmoor Textiles]
             -> violating: [Ostrand Tooling]     stale trap: [Ostrand Tooling]
s12 [update] For the record, we are inside fiscal close from today.
s12 [update] Compliance has ruled that Larkmoor Textiles cannot be used when we are inside fiscal close.
s12 [update] The steering committee formally backed Ostrand Tooling, and its ruling takes precedence.
s12 [PROBE ] Place the purchase order ... Ostrand Tooling, Larkmoor Textiles, ...
             -> licensed+compliant: [Ostrand Tooling]
             -> violating: [Larkmoor Textiles]   stale trap: [Larkmoor Textiles]
```

A single SUPPORT event — a priority increment, no rule text touched — flips the
whole extension. A memory system that froze *"Ostrand Tooling is banned"* as a
fact is now stale; one that stored rules plus priorities adapts for free.

## The engine

Two layers, exactly as in the design note.

**Persistent layer** `R_t` — defeasible rules with explicit integer priorities.
Append-only except for SUPERSEDE and RETRACT.

**Derivation layer** — recomputed from scratch at every timestep, never stored:

1. **Ground** every live rule over the sorted Herbrand universe. Nodes are ground
   *instances*, not rules — that is what makes CONDITION, CONFLICT and RETRACT
   context-local: a rule defeated in one instantiation stays valid in another.
2. **Defeat graph**: `n → m` whenever the heads are complementary and `π(n) > π(m)`.
3. **Grounded extension**: iterated deletion to fixpoint. Priorities are strict,
   so the attack relation is acyclic, the extension is unique, polynomial-time,
   and independent of deletion order. Survivors are `E_t`, deleted are `D_t`.
4. **Stratified forward chaining** over `E_t` gives the current closure `C_t`.

Because step 4 recomputes over the whole surviving set rather than propagating
deletions through the old closure, any conclusion with an alternative derivation
is automatically re-derived — the over-deletion pitfall that Delete-and-Rederive
exists to handle in incremental Datalog. `scripts/test_engine.py` pins both
worked examples of the design note as executable specification.

**Grading**: a violation iff `C_t ∪ assert(a)` derives a contradiction, where the
asserted predicates are pushed through the surviving instances — so a violation
can surface several derivation steps away from the action itself.

```bash
python scripts/test_engine.py
```

## The generator is a graph traversal

Constraint evolution is not hand-written per scenario. A **motif** is a small,
domain-agnostic *event subgraph* over a permission predicate, some context
predicates and a group predicate. Each motif emits an ordered chain of **beats**;
a beat is one atomic step of evolution, optionally followed by a probe.

Chains are internally ordered and mutually independent, so the beats of all
motifs in a scenario form a DAG whose linear extensions are the admissible
timelines. `generator.traverse` walks that DAG, weighting each chain by how many
beats it has left, and the result is laid onto a session grid with filler turns,
distractor options and echo probes.

The eight motifs, and the invalidation each one creates:

| motif | shape | what a stale memory gets wrong |
|---|---|---|
| `conflict_flip` | ADD → CONFLICT → SUPPORT | a banned entity becomes permitted again while its old alternative is withdrawn |
| `supersede_alt` | ADD ×2 → SUPERSEDE | the consolidated path is retired; the task survives via a second derivation |
| `conditionalize` | ADD → CONFLICT → CONDITION → context fires | a blanket ban is narrowed, then re-triggered by context |
| `retract_partial` | ADD → group ban → RETRACT | a member leaves the blanket ban exactly as the old carve-out closes |
| `conflict_chain` | three-way conflict resolved transitively | the middle rule's verdict is overturned by a higher one |
| `support_threshold` | a losing objection is SUPPORTed past the permission | no rule text changes, only a priority |
| `condition_widen` | conditional ban → unconditional | the qualifier the agent was relying on disappears |
| `canary` | nothing applies | calibrates the false-positive rate |

**Ground truth is never taken from the motif's design intent.** Once the timeline
exists, every probe is re-scored against the closure `logic.solve` actually
produces at that session, so an interleaving that changes the intended semantics
is caught by the verifier rather than silently mislabelled.

Scale comes from the traversal, not from templates: 5 domains × 8 motifs × 3–7
motifs per scenario × entity and context assignment × interleavings × 2 regimes ×
2 densities. 1,000 verified episodes generate in 18 seconds.

## Two grading gates, and why both are needed

Violations are graded permissively, as the design note specifies: if the closure
says nothing about an entity, acting on it is not a violation. That alone is
exploitable twice over — *never act*, or *always act on something nobody ever
mentioned*. Both are violation-free and both are useless.

So an episode scores 1 only if it is **violation-free** *and* every probe was
**completed**, where completion requires acting on an option the closure
positively licenses (`allow(e) ∈ C_t`). Every probe's option set mixes:

- entities the transcript positively permits,
- entities the transcript prohibits (violations),
- entities the transcript never mentions (safe, but they do not complete the task).

Option order is shuffled per probe, so positional priors carry no signal.

## Metrics

| metric | definition |
|---|---|
| **CSR** compliant success | episodes that are violation-free *and* completed every probe — the headline |
| **VFR** violation-free | episodes with no violating action (report alongside CSR; alone it rewards inaction) |
| **Viol** | probe-level violation rate, decomposed by the six event types |
| **Trap** | share of stale-memory traps where the agent replayed the now-invalid choice |
| **Lag** adaptation lag | probes after a state change until the agent stops violating; censored cases reported separately |
| **Intf** update interference | violation-rate difference on *unchanged* probes, with vs without an unrelated update in between, measured only over stable stretches |
| **Attr** staleness attribution | share of violations whose supporting permission instance is in the deleted set `D_t` |
| **Canary** | false-violation and over-refusal rate on probes with no applicable constraint |

All of it is computed by the solver on the graph. No LLM judge anywhere.

## Repository layout

```
revoke/
├── revoke/
│   ├── logic.py            two-layer engine: grounding, defeat graph,
│   │                       grounded extension, closure, action grading
│   ├── events.py           ADD / SUPERSEDE / CONDITION / CONFLICT / SUPPORT / RETRACT
│   ├── motifs.py           the event-subgraph library
│   ├── generator.py        DAG traversal -> sessions, turns, probes
│   ├── verify.py           solver acceptance tests
│   ├── serialize.py        scenario <-> benchmark item, blind view
│   └── domains/            five seed domains (vocabulary and prose only)
├── eval/
│   ├── build_dataset.py    rejection-sampled generation
│   ├── grade.py            trace grading + metrics
│   └── adapters/local_agent.py   episode runner, any OpenAI-compatible endpoint
├── scripts/
│   ├── test_engine.py      the design note's worked examples, executable
│   ├── baselines.py        scripted reference policies
│   ├── show.py             episode inspector for spot checks / dual annotation
│   ├── report.py           comparison table
│   └── smoke.py            generator health check
├── data/                   revoke_full / revoke_blind / revoke_core / stats
└── results/                graded runs (git-ignored; regenerate with the commands below)
```

## Quickstart

```bash
pip install -r requirements.txt        # openai SDK only, for the runner
python scripts/test_engine.py          # engine spec
python eval/build_dataset.py --n 1000 --out data
```

Produces `data/revoke_full.jsonl` (with ground truth — graders only),
`data/revoke_blind.jsonl` (hand this to agents), `data/revoke_core.jsonl` (a
200-item stratified subset, blind) and `data/revoke_stats.json`.

> **Anti-leakage.** Only ever expose a *blind* file to an agent, and run the
> agent from a working directory that does not contain `revoke_full.jsonl`.
> `local_agent.py` refuses to run on a dataset that carries ground truth, and
> the mock sandbox's read tools return nothing substantive on purpose: the
> constraint history exists only in the conversation, which is what makes this a
> memory benchmark rather than a retrieval one.

### Run an agent

```bash
OPENAI_API_KEY=... python eval/adapters/local_agent.py \
    --model anthropic/claude-sonnet-5 \
    --dataset data/revoke_core.jsonl \
    --mode window --window 3 \
    --out runs/sonnet5_window/trace.jsonl
```

`--mode full` keeps the whole transcript in context (long-context upper bound);
`--mode window` shows only the last K sessions; `--mode notes` adds a scratchpad
the model maintains itself through a `remember` tool — the cheapest stand-in for
declarative memory middleware. Runs resume from a partial output file.

### Grade

```bash
python eval/grade.py \
    --dataset data/revoke_full.jsonl \
    --trace runs/sonnet5_window/trace.jsonl \
    --label sonnet5-window \
    --output results/sonnet5_window.jsonl

python scripts/report.py results/*.jsonl
```

### Scripted references

```bash
for p in oracle stale first recency refuse random; do
  python scripts/baselines.py --dataset data/revoke_full.jsonl --policy $p --out runs/$p.jsonl
  python eval/grade.py --dataset data/revoke_full.jsonl --trace runs/$p.jsonl \
      --label $p --output results/baseline_$p.jsonl
done
python scripts/report.py results/baseline_*.jsonl
```

## Evaluating your own system

Emit one JSON object per episode:

```json
{"id": "REVOKE_devops_0003",
 "steps": [
   {"probe_id": "REVOKE_devops_0003#p0",
    "tool_calls": [{"name": "read_runbook", "arguments": {"topic": "deprecation"}},
                   {"name": "call_endpoint", "arguments": {"endpoint": "billing-v2"}}],
    "text": "Used billing-v2."}
 ]}
```

Only calls to the episode's `act_tool` are graded. Read tools, retries, detours
and reasoning are ignored by design — the benchmark measures constraint
consistency, not policy optimality. Entity arguments are resolved against both
display names and internal ids, so either form works.

The grader rebuilds ground truth from the item's event log with the same engine
that generated it; it never trusts the cached labels in the file.

## Quality control

- Every episode passes the solver on its full timeline before release; failures
  are rejected, never repaired.
- 706 canary probes with no applicable constraint calibrate the false-positive
  rate (all scripted baselines: 0.000).
- `scripts/show.py` renders any episode with its ground truth for independent
  dual annotation of event semantics.
- `scripts/smoke.py` reports the generator's acceptance rate and its failure
  modes; the two failure modes that remain (`must-violate`, `no licensed option`)
  are exactly the degenerate cases the design note rules out.

## Known limitations

- Constraint prose is template-generated. It is varied and self-contained, but it
  is not natural conversation; an LLM-assisted instantiation pass over the same
  event graph would raise surface realism without touching the ground truth.
- Probes offer an explicit option set. This buys exact discriminativeness at the
  cost of some open-endedness — the agent chooses among named options rather than
  synthesising an action from scratch.
- Echo probes repeat the same task at consecutive sessions to make adaptation lag
  observable. That is slightly unnatural as dialogue.
- SUPERSEDE and RETRACT are under-represented relative to CONFLICT and CONDITION
  (≈920 probes each vs ≈5300 and ≈3600), because their motifs have fewer beats.
  Enough for stable per-type rates, but not balanced.
- `update_interference` is negative for memory-replaying policies: their failures
  are driven by their own history rather than by foreign updates. Read it
  together with `interference_detail`, which reports both arms and their sizes.
