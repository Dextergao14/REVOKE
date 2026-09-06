import sys, collections
from revoke.domains.seeds import ALL
from revoke.generator import build_scenario
from revoke.verify import verify

ok = bad = 0
fails = collections.Counter()
stats = collections.Counter()
for i in range(200):
    dom = list(ALL.values())[i % 5]
    regime = "short" if i % 2 else "long"
    dens = "sparse" if i % 3 else "dense"
    sc = build_scenario(dom, f"S{i:04d}", seed=1000 + i, regime=regime, density=dens)
    r = verify(sc, dom.allow)
    if r.ok:
        ok += 1
        for k, v in r.stats["by_event"].items(): stats[k] += v
        stats["trap"] += r.stats["trap_probes"]; stats["probes"] += r.stats["probes"]
    else:
        bad += 1
        for f in r.failures: fails[f.split(":")[-1].strip()[:60]] += 1
print("pass", ok, "fail", bad)
print("failure modes:", fails.most_common(8))
print("events:", dict(stats))
