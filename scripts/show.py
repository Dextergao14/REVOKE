#!/usr/bin/env python3
"""Pretty-print one episode with its ground truth, for spot checks and for the
independent dual annotation pass."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

C = {"UPD": "\033[36m", "PRO": "\033[33m", "FIL": "\033[90m", "0": "\033[0m",
     "V": "\033[31m", "G": "\033[32m"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/revoke_full.jsonl")
    ap.add_argument("--id", default="")
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--plain", action="store_true")
    a = ap.parse_args()
    if a.plain:
        for k in C:
            C[k] = ""
    rows = [json.loads(l) for l in open(a.dataset)]
    it = next((r for r in rows if r["id"] == a.id), None) if a.id else rows[a.index]
    n = it["entity_names"]
    print(f"{it['id']}  {it['domain_title']}  regime={it['regime']} "
          f"density={it['density']}  motifs={','.join(it['motifs'])}")
    print(f"{it['n_sessions']} sessions, {len(it['probes'])} probes, "
          f"{len(it['events'])} constraint events\n")
    pm = {p["probe_id"]: p for p in it["probes"]}
    for s in it["sessions"]:
        for t in s["turns"]:
            tag = t["kind"][:3].upper()
            print(f"{C[tag]}s{s['index']:>2} [{tag}] {t['text']}{C['0']}")
            if t.get("probe_id"):
                p = pm[t["probe_id"]]
                print(f"        tests={p['tests']} ({p['motif_name']})")
                print(f"        {C['G']}licensed+compliant: "
                      f"{[n[e] for e in p['licensed']]}{C['0']}")
                print(f"        {C['V']}violating: "
                      f"{[n[e] for e in p['violating']]}{C['0']}"
                      f"   safe-but-unlicensed: "
                      f"{[n[e] for e in p['compliant'] if e not in p['licensed']]}")
                if p["stale_trap"]:
                    print(f"        {C['V']}stale trap (was compliant last time): "
                          f"{[n[e] for e in p['stale_trap']]}{C['0']}")
                print(f"        deleted instances D_t: {p['deleted_rules']}")


if __name__ == "__main__":
    main()
