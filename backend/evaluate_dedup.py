"""Measure deduplication accuracy against the generator's ground truth.

The sample generator plants exactly 20 duplicates among 170 unique people (+10 junk rows) and tags
every record with `_person_id`. This script runs the matcher at several thresholds and reports
true merges, wrong merges (different people merged) and missed duplicates, for:
  * the OLD rule  : exact email/phone, or composite token_sort_ratio >= threshold (name-blind)
  * the NEW rule  : exact email/phone, or guarded fuzzy match (app/services/match_rules.py)

It uses no database. Run:  python evaluate_dedup.py            (prints a Markdown report)
                           python evaluate_dedup.py --write    (also saves docs/dedup_evaluation.md)
"""
import os
import sys
from collections import defaultdict
from itertools import combinations

from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.cleaning_service import is_junk_lead, normalize_company, normalize_phone  # noqa: E402
from app.services.fast_dedup import fast_deduplicate_leads, get_blocking_keys  # noqa: E402
from app.services.match_rules import composite_string  # noqa: E402
from app.services.sample_generator import generate_sample_leads  # noqa: E402

THRESHOLDS = [75.0, 80.0, 85.0, 90.0, 95.0]


def prepared_leads():
    leads = []
    for i, r in enumerate(generate_sample_leads(200)):
        email = (r.get("email") or "").strip().lower() or None
        phone = normalize_phone(r.get("phone")) or None
        company = normalize_company(r.get("company"))
        junk, _ = is_junk_lead(r.get("first_name"), r.get("last_name"), email, company, phone)
        leads.append({**r, "email": email, "phone": phone, "company": company, "row_index": i + 2,
                      "is_junk": junk})
    return leads


def true_pairs(leads):
    by_person = defaultdict(list)
    for l in leads:
        by_person[l["_person_id"]].append(l["row_index"])
    return {tuple(sorted(p)) for rows in by_person.values() for p in combinations(rows, 2)}


def clusters_to_pairs(groups):
    return {tuple(sorted(p)) for g in groups for p in combinations(g, 2)}


def old_rule_pairs(leads, threshold):
    """Reproduces the previous name-blind behaviour for comparison."""
    cand = [l for l in leads if not l["is_junk"]]
    parent = list(range(len(cand)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(j)] = find(i)

    seen = {}
    for idx, l in enumerate(cand):
        for key in ("email", "phone"):
            v = l.get(key)
            if v:
                if (key, v) in seen:
                    union(seen[(key, v)], idx)
                else:
                    seen[(key, v)] = idx
    buckets = defaultdict(list)
    for idx, l in enumerate(cand):
        for k in get_blocking_keys(l):
            buckets[k].append(idx)
    comp = [composite_string(l) for l in cand]
    borderline = []
    for idxs in buckets.values():
        for a, b in combinations(idxs, 2):
            if find(a) != find(b):
                s = fuzz.token_sort_ratio(comp[a], comp[b])
                if s >= threshold:
                    union(a, b)
                    borderline.append((s, cand[a], cand[b]))
    groups = defaultdict(list)
    for idx in range(len(cand)):
        groups[find(idx)].append(cand[idx]["row_index"])
    return clusters_to_pairs(groups.values()), borderline


def new_rule_pairs(leads, threshold):
    copies = [dict(l) for l in leads]
    _, logs, _ = fast_deduplicate_leads(copies, "evaluation", threshold=threshold)
    groups = defaultdict(set)
    for m in logs:
        groups[m["winner_raw_lead_id"]].update({m["winner_raw_lead_id"], m["archived_raw_lead_id"]})
    return clusters_to_pairs(groups.values()), logs


def metrics(pred, truth):
    tp, fp, fn = len(pred & truth), len(pred - truth), len(truth - pred)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return tp, fp, fn, precision, recall


def report():
    leads = prepared_leads()
    truth = true_pairs(leads)
    by_row = {l["row_index"]: l for l in leads}
    name = lambda r: f"{by_row[r]['first_name']} {by_row[r]['last_name']} ({by_row[r]['company']})"  # noqa: E731
    out = ["# Deduplication evaluation", "",
           f"Dataset: `generate_sample_leads(200)` (seed 42): {len(leads)} rows, {len(truth)} planted duplicate pairs.",
           "A *wrong merge* joins two different people; a *missed duplicate* leaves a planted pair unmerged.", "",
           "| Rule | Threshold | Correct merges | Wrong merges | Missed duplicates | Precision | Recall |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    old85_fp = []
    for rule in ("old", "new"):
        for t in THRESHOLDS:
            pred, extra = (old_rule_pairs if rule == "old" else new_rule_pairs)(leads, t)
            tp, fp, fn, p, r = metrics(pred, truth)
            label = "Old (composite only)" if rule == "old" else "New (guarded)"
            out.append(f"| {label} | {t:.0f}% | {tp} | {fp} | {fn} | {p:.0%} | {r:.0%} |")
            if rule == "old" and t == 85.0:
                old85_fp = sorted(pred - truth)
    out += ["", "## Examples of wrong merges made by the old rule at 85%", ""]
    for a, b in old85_fp[:10]:
        s = fuzz.token_sort_ratio(composite_string(by_row[a]), composite_string(by_row[b]))
        out.append(f"* {name(a)} <-> {name(b)}: composite similarity {s:.1f}%")
    _, logs = new_rule_pairs(leads, 85.0)
    exact = sum(1 for m in logs if m["merge_reason"].startswith("Exact"))
    out += ["", "## Real merges made by the new rule at 85% (from the merge log)", "",
            f"{len(logs)} merges: {exact} by exact email/phone match, {len(logs) - exact} by the guarded fuzzy rule. "
            "On this dataset every planted duplicate still shares an email or phone with its original, so the "
            "fuzzy path is exercised separately by unit tests (tests/test_dedup_rules.py).", "",
            "| Archived record | Kept record | Score | Reason |", "|---|---|---:|---|"]
    for m in sorted(logs, key=lambda m: (m["similarity_score"], m["archived_raw_lead_id"])):
        out.append(f"| {name(m['archived_raw_lead_id'])} | {name(m['winner_raw_lead_id'])} | "
                   f"{m['similarity_score']}% | {m['merge_reason'].split('. Merged')[0]} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    text = report()
    print(text)
    if "--write" in sys.argv:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "dedup_evaluation.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Saved {os.path.abspath(path)}")
