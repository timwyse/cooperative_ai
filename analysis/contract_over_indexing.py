"""
Do models over-index on their contracts when deciding whether to trade?

This script compares two contract regimes, across every *self-play* model pair
in the reduced-config runs:

    - ctx1_fog00_p4ptrue_contract_tile_with_judge_implementation_selfish11
    - ctx1_fog00_p4ptrue_contract_strict_selfish11

For each "decline-to-trade" decision we measure how often the agent's
rationale invokes a *pre-existing contract* as the justification:

    - TRADE_PROPOSAL with parsed["want_to_trade"] == False
    - TRADE_RESPONSE with parsed["status"] == "rejected"

A higher rate in the tile_with_judge regime is evidence that the model is
"over-indexing" on the contract (leaning on it to justify not trading) versus
the strict regime, where rationales more often reason directly about
inventory / path.

Self-play only (model X vs model X); cross-model pairings are skipped.

Usage:
    python analysis/contract_over_indexing.py
    python analysis/contract_over_indexing.py --scenario Mutual_Dependency
    python analysis/contract_over_indexing.py --show-misses 3
"""

import argparse
import glob
import json
import os
import re
from collections import defaultdict

# Root of the reduced-config runs (one dir per model pairing).
DEFAULT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public_logs",
    "reduced_config_runs",
)

CONFIGS = {
    "tile_with_judge": "ctx1_fog00_p4ptrue_contract_tile_with_judge_implementation_selfish11",
    "strict": "ctx1_fog00_p4ptrue_contract_strict_selfish11",
}

# Regex that matches references to a *pre-existing* contract / agreement that
# the agent already has in place. We deliberately tie these phrases to a
# standing agreement (contract / agreed / promised / our deal / coverage from
# the other player) so we don't pick up the agent merely describing the *new*
# offer it is currently evaluating (which it often calls "this arrangement").
CONTRACT_PATTERNS = [
    r"\bcontract\b",
    r"\bbinding\b",
    r"\b(?:already|we['’`]?ve|i['’`]?ve|have)\s+agreed\b",
    r"\bagreed[\s-]?(?:upon|contract|arrangement|path|to)\b",
    r"\bagreement\b",
    r"\bpromis(?:e|ed|es|ing)\b",
    r"\bcover(?:s|ed|age|ing)?\s+(?:by|from|me|my|for me)\b",
    r"\b(?:our|the)\s+(?:deal|arrangement|agreement|coverage)\b",
    r"\bexisting\s+(?:contract|arrangement|agreement|deal)\b",
    r"\bother player\b.*\bcover",
    r"\bcover\b.*\bother player\b",
]

CONTRACT_RE = re.compile("|".join(CONTRACT_PATTERNS), re.IGNORECASE)

# Per-keyword regexes, used only for a transparency breakdown of what is
# driving the matches.
KEYWORD_RES = {
    "contract": re.compile(r"\bcontract\b", re.IGNORECASE),
    "agreed/agreement": re.compile(r"\bagree", re.IGNORECASE),
    "promise(d)": re.compile(r"\bpromis", re.IGNORECASE),
    "binding": re.compile(r"\bbinding\b", re.IGNORECASE),
    "cover(age)": re.compile(r"\bcover", re.IGNORECASE),
}


def discover_self_play_models(root):
    """Return sorted model names for self-play pairings (model X vs model X)."""
    models = []
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if not os.path.isdir(full) or "-" not in entry:
            continue
        a, _, b = entry.partition("-")
        if a == b:
            models.append(entry)
    return models


def iter_decline_decisions(model_dir, scenario, config_dir_name):
    """Yield (action_type, rationale) for every decline-to-trade decision."""
    pattern = os.path.join(model_dir, scenario, "*", config_dir_name, "*", "verbose_log*.json")
    for path in sorted(glob.glob(pattern)):
        with open(path) as fh:
            data = json.load(fh)
        turns = data.get("game", {}).get("turns", {})
        for turn in turns.values():
            for action in turn.get("actions", []):
                resp = action.get("agent_response") or {}
                parsed = resp.get("parsed")
                if not isinstance(parsed, dict):
                    continue
                atype = action.get("action_type")
                rationale = parsed.get("rationale", "") or ""
                if atype == "TRADE_PROPOSAL" and parsed.get("want_to_trade") is False:
                    yield "TRADE_PROPOSAL", rationale
                elif atype == "TRADE_RESPONSE" and parsed.get("status") == "rejected":
                    yield "TRADE_RESPONSE", rationale


def analyze(model_dir, scenario, config_dir_name, show_misses=0):
    # counts[action_type] = [n_total, n_mention]
    counts = defaultdict(lambda: [0, 0])
    keyword_hits = defaultdict(int)
    misses = []

    for atype, rationale in iter_decline_decisions(model_dir, scenario, config_dir_name):
        counts[atype][0] += 1
        if CONTRACT_RE.search(rationale):
            counts[atype][1] += 1
            for kw, kre in KEYWORD_RES.items():
                if kre.search(rationale):
                    keyword_hits[kw] += 1
        elif len(misses) < show_misses:
            misses.append((atype, rationale))

    return counts, keyword_hits, misses


def pct(num, den):
    return (100.0 * num / den) if den else 0.0


def totals(counts):
    n = sum(t for t, _ in counts.values())
    m = sum(c for _, c in counts.values())
    return n, m


def print_config_report(label, counts, keyword_hits, misses):
    print(f"\n  -- {label} --")
    total_n, total_m = totals(counts)
    header = f"  {'decision type':<18}{'declines':>10}{'cite contract':>16}{'rate':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for atype in ("TRADE_PROPOSAL", "TRADE_RESPONSE"):
        n, m = counts.get(atype, [0, 0])
        print(f"  {atype:<18}{n:>10}{m:>16}{pct(m, n):>9.1f}%")
    print("  " + "-" * (len(header) - 2))
    print(f"  {'ALL':<18}{total_n:>10}{total_m:>16}{pct(total_m, total_n):>9.1f}%")

    if keyword_hits:
        kb = ", ".join(f"{kw}={c}" for kw, c in sorted(keyword_hits.items(), key=lambda x: -x[1]))
        print(f"  keywords (of citing): {kb}")

    if misses:
        print(f"  examples NOT citing a contract ({len(misses)}):")
        for atype, rationale in misses:
            snippet = rationale.strip().replace("\n", " ")[:160]
            print(f"    [{atype}] {snippet}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=DEFAULT_ROOT, help="reduced_config_runs root")
    ap.add_argument("--scenario", default="Mutual_Dependency",
                    help="Scenario subfolder (e.g. Mutual_Dependency)")
    ap.add_argument("--show-misses", type=int, default=3,
                    help="How many non-citing rationales to print per config")
    args = ap.parse_args()

    models = discover_self_play_models(args.root)

    # summary[model][config] = (counts, total_n, total_m)
    summary = {}
    for model in models:
        model_dir = os.path.join(args.root, model)
        per_config = {}
        for label, cfg in CONFIGS.items():
            counts, kw, misses = analyze(model_dir, args.scenario, cfg, args.show_misses)
            per_config[label] = (counts, kw, misses)
        # Skip models that produced no decline decisions at all for this scenario.
        if all(totals(c[0])[0] == 0 for c in per_config.values()):
            continue
        summary[model] = per_config
        print(f"\n{'=' * 72}\n{model}  (scenario: {args.scenario})\n{'=' * 72}")
        for label in CONFIGS:
            counts, kw, misses = per_config[label]
            print_config_report(f"{label}  ({CONFIGS[label]})", counts, kw, misses)

    # Cross-model comparison table.
    print(f"\n{'=' * 72}\nCOMPARISON: % of declines citing a pre-existing contract  (scenario: {args.scenario})\n{'=' * 72}")
    head = (f"{'model (self-play)':<26}{'tile_with_judge':>20}{'strict':>20}{'delta':>10}")
    print(head)
    print("-" * len(head))
    agg = {"tile_with_judge": [0, 0], "strict": [0, 0]}
    for model in summary:
        rates = {}
        for label in CONFIGS:
            counts = summary[model][label][0]
            n, m = totals(counts)
            rates[label] = (pct(m, n), m, n)
            agg[label][0] += m
            agg[label][1] += n
        tj = rates["tile_with_judge"]
        st = rates["strict"]
        delta = tj[0] - st[0]
        short = model.split("-")[0]
        print(f"{short:<26}"
              f"{f'{tj[0]:.1f}% ({tj[1]}/{tj[2]})':>20}"
              f"{f'{st[0]:.1f}% ({st[1]}/{st[2]})':>20}"
              f"{f'{delta:+.1f}pp':>10}")
    print("-" * len(head))
    tj_m, tj_n = agg["tile_with_judge"]
    st_m, st_n = agg["strict"]
    tj_all = pct(tj_m, tj_n)
    st_all = pct(st_m, st_n)
    print(f"{'ALL MODELS':<26}"
          f"{f'{tj_all:.1f}% ({tj_m}/{tj_n})':>20}"
          f"{f'{st_all:.1f}% ({st_m}/{st_n})':>20}"
          f"{f'{tj_all - st_all:+.1f}pp':>10}")


if __name__ == "__main__":
    main()
