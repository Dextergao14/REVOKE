# Vendored: EvolveLab's DILU memory provider (from MemEvolve)

Source repository: https://github.com/bingreeky/MemEvolve (ICML'26, "MemEvolve: Meta-Evolution of
Agent Memory Systems"), commit `6035d5659d7a092dbfa6a87b1a32a3cee652ba54` (2026-05-05).
License: Apache-2.0 (see `LICENSE` in this directory, copied from the repository root).

Files copied **byte for byte** from `Flash-Searcher-main/EvolveLab/`:

| here | upstream |
|---|---|
| `EvolveLab/__init__.py` | `EvolveLab/__init__.py` |
| `EvolveLab/base_memory.py` | `EvolveLab/base_memory.py` |
| `EvolveLab/memory_types.py` | `EvolveLab/memory_types.py` |
| `EvolveLab/providers/dilu_memory_provider.py` | `EvolveLab/providers/dilu_memory_provider.py` |

`EvolveLab/providers/__init__.py` is REVOKE's own (upstream's imports every provider and their
dependencies; only DILU is needed here). Nothing in the vendored files is edited; every adaptation
lives in `eval/memory/dilu.py`, which subclasses `DiluMemoryProvider` and overrides only
`initialize`, `_load_memories_from_json`, `_save_memories_to_json` and
`_summarize_trajectory_with_llm` (the last one to remove the success/failure label REVOKE cannot
supply). DILU itself: Wen et al., "DiLu: A Knowledge-Driven Approach to Autonomous Driving with
Large Language Models", ICLR 2024, arXiv:2309.16292.
