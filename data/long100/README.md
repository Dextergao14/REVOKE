# REVOKE long tier — 100 episodes, 300k–900k tokens

Each episode is one continuous record of 420–650 sessions in one of six worlds,
rendered as the document that history would live in and padded to a length
band.  The constraint history (events), the per-session closure and every
generated task are the episode; the released probes are one selection from
that pool.

## Layout

```
data/long100/
  manifest.jsonl               one row per episode (see below)
  episodes/<id>_blind.jsonl.gz what an agent under test may see
  episodes/<id>_full.jsonl.gz  ground truth: events, timeline, probes, probe_pool
  README.md
```

The transcripts are too large for git; the manifest, the generator and the
seeds are committed, and `python3 eval/build_long.py --n 100 --jobs 8 --out
data/long100` regenerates the set byte for byte.

## Bands

| target | cycles | probes / episode | worlds |
|---|---|---|---|
| 300k | 6 | 10 | all six, round-robin |
| 450k | 7 | 11 | |
| 600k | 8 | 12 | |
| 750k | 9 | 13 | |
| 900k | 10 | 15 | |

`cycles` repeats the flip-style motifs' state arcs, so the rule density stays
roughly constant along the ladder; rendered length lands within about 5% of
the target (real prompt tokens are within 3% of the character estimate).

## Manifest row

`id, world, layout (sectioned|flat), target_tokens, tokens, sessions, cycles,
probes, traps, far (recall span > 200), mean_weight, crutch (released tasks
whose licensed options were all approved long ago and never restricted; the
selector avoids them), pool (size of probe_pool), seed, rejections (seeds
discarded by the acceptance checks before this one), pad_dup, sha256_blind`.

## Asking different questions of the same episode

`probe_pool` in the full item holds every task the generator emitted for the
episode — typically 180–270 — each with its session, option set, licensed and
violating options, blamed rules, stale-trap label, difficulty features and the
rendered task text.  `scripts/reselect_probes.py` builds a new full/blind pair
from any selection:

```
python3 scripts/reselect_probes.py --full data/long100/episodes/<id>_full.jsonl.gz \
    --k 12 --strategy traps --out data/long100/reselect/
```

Ground truth does not change: the grader rebuilds the closure at each task's
session from the events, so a reselected item is graded by the same code.

## Grading

```
python3 eval/adapters/episode_runner.py --blind data/long100/episodes/<id>_blind.jsonl.gz ...
python3 scripts/long_report.py --full data/long100/episodes/<id>_full.jsonl.gz --runs runs/...
```

Only blind files may reach an agent; the runners refuse a file whose name
says `full` or whose probes carry labels.
