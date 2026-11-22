import re
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.services.match_rules import composite_string, fuzzy_match, REVIEW_BAND, classify_fuzzy_score

GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "proton.me", "protonmail.com", "mail.com", "zoho.com"
}

def get_blocking_keys(lead: Dict[str, Any]) -> List[str]:
    """
    Computes blocking keys to partition candidates into small buckets for high-speed fuzzy comparison.
    Uses fine-grained blocking:
      1. Domain + first-name initial (df:{domain}:{fn[0]})
      2. Company prefix + first-name initial (cf:{comp[:4]}:{fn[0]})
      3. Phone suffix last 4 digits (ph4:{phone[-4:]})
      4. Last name prefix + first-name initial (nf:{ln[:4]}:{fn[0]})
    Eliminates broad fallbacks (like state) that caused catastrophic O(N^2) comparison explosions.
    """
    keys = []
    email = lead.get("email") or ""
    fn = (lead.get("first_name") or lead.get("full_name") or "").strip().lower()
    fn_char = fn[0] if fn else ""

    if "@" in email:
        domain = email.split("@")[-1].lower().strip()
        if domain and domain not in GENERIC_DOMAINS:
            if fn_char:
                keys.append(f"df:{domain}:{fn_char}")
            else:
                keys.append(f"dom:{domain}")

    comp = (lead.get("company") or "").lower().strip()
    if comp:
        comp_prefix = "".join(c for c in comp if c.isalnum())[:4]
        if comp_prefix:
            if fn_char:
                keys.append(f"cf:{comp_prefix}:{fn_char}")
            else:
                keys.append(f"comp:{comp_prefix}")

    phone_raw = re.sub(r"\D", "", str(lead.get("phone") or ""))
    if len(phone_raw) >= 4:
        keys.append(f"ph4:{phone_raw[-4:]}")

    ln = (lead.get("last_name") or "").strip().lower()
    ln_prefix = "".join(c for c in ln if c.isalnum())[:4]
    if ln_prefix and fn_char:
        keys.append(f"nf:{ln_prefix}:{fn_char}")

    return keys

def score_lead_completeness(lead: Dict[str, Any]) -> float:
    """Calculates priority score for picking cluster winner."""
    fields = [
        lead.get("first_name"), lead.get("last_name"), lead.get("email"),
        lead.get("company"), lead.get("job_title"), lead.get("phone"),
        lead.get("state"), lead.get("industry"), lead.get("company_size")
    ]
    comp_ratio = sum(1 for f in fields if f and str(f).strip() not in {"", "None", "nan", "UNKNOWN"}) / len(fields)
    eng = float(lead.get("engagement_score") or 0.0)
    return (comp_ratio * 100.0) + (eng / 10.0)

def fast_deduplicate_leads(
    leads: List[Dict[str, Any]],
    run_id: str,
    threshold: float = 85.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    High-Performance 2-Pass Deduplication:
    Pass 1: Exact-match hash lookup on normalized email and phone (O(N)).
    Pass 2: RapidFuzz token_sort_ratio inside blocking buckets (O(K^2) per bucket).
    
    Guarantees processing 10,000+ leads in seconds without quadratic explosion.
    Returns:
      (winner_leads, merged_logs, dedup_stats)
    """
    if not leads:
        return [], [], {"total_clusters": 0, "duplicates_merged": 0}

    # Separate junk and non-junk
    junk_leads = [l for l in leads if l.get("is_junk")]
    clean_candidates = [l for l in leads if not l.get("is_junk")]

    # Union-Find (Disjoint Set) to track clusters efficiently
    parent = list(range(len(clean_candidates)))

    def find(i: int) -> int:
        path = []
        while parent[i] != i:
            path.append(i)
            i = parent[i]
        for node in path:
            parent[node] = i
        return i

    def union(i: int, j: int):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_j] = root_i

    # PASS 1: Exact Hash Lookups (Email & Phone)
    email_to_idx: Dict[str, int] = {}
    phone_to_idx: Dict[str, int] = {}
    # Every edge that joined two records, keyed by (min_idx, max_idx) list positions -> (score, reason)
    edges: Dict[Tuple[int, int], Tuple[float, str]] = {}

    for idx, lead in enumerate(clean_candidates):
        em = lead.get("email")
        if em:
            if em in email_to_idx:
                prev_idx = email_to_idx[em]
                union(prev_idx, idx)
                edges[(prev_idx, idx)] = (100.0, f"Exact match on email address ({em})")
            else:
                email_to_idx[em] = idx

        ph = lead.get("phone")
        if ph:
            if ph in phone_to_idx:
                prev_idx = phone_to_idx[ph]
                union(prev_idx, idx)
                edges.setdefault((prev_idx, idx), (100.0, f"Exact match on E.164 phone number ({ph})"))
            else:
                phone_to_idx[ph] = idx

    # PASS 2: Guarded fuzzy matching inside blocking buckets.
    # A fuzzy match needs the same last name, a near-identical first name and the same company/domain
    # (see match_rules.py) before the composite similarity threshold is even considered.
    bucket_map: Dict[str, List[int]] = defaultdict(list)
    for idx, lead in enumerate(clean_candidates):
        for b_key in get_blocking_keys(lead):
            bucket_map[b_key].append(idx)

    composite_strings = [composite_string(l) for l in clean_candidates]
    # Borderline guarded pairs (REVIEW_BAND) are not merged; they are returned for human review.
    review_candidates: List[Tuple[int, int, float, str]] = []

    for b_key, indices in bucket_map.items():
        n_in_bucket = len(indices)
        if n_in_bucket <= 1:
            continue

        # Cap bucket comparison at 100 to guard against catastrophic O(N^2) outliers
        target_indices = indices[:100] if n_in_bucket > 100 else indices
        n_eval = len(target_indices)

        for i_pos in range(n_eval):
            i_idx = target_indices[i_pos]
            for j_pos in range(i_pos + 1, n_eval):
                j_idx = target_indices[j_pos]
                if find(j_idx) == find(i_idx):
                    continue  # already in same cluster
                ok, sim, reason = fuzzy_match(clean_candidates[i_idx], clean_candidates[j_idx], REVIEW_BAND[0],
                                              composite_strings[i_idx], composite_strings[j_idx])
                decision = classify_fuzzy_score(sim, threshold) if ok else "none"
                if decision == "merge":
                    union(i_idx, j_idx)
                    edges[(min(i_idx, j_idx), max(i_idx, j_idx))] = (sim, f"Fuzzy match: {reason}")
                elif decision == "review":
                    review_candidates.append((i_idx, j_idx, sim, reason))

    # Group records by root parent
    clusters: Dict[int, List[int]] = defaultdict(list)
    for idx in range(len(clean_candidates)):
        clusters[find(idx)].append(idx)

    winner_leads: List[Dict[str, Any]] = []
    merged_logs: List[Dict[str, Any]] = []
    duplicate_records_merged = 0

    for root_id, member_indices in clusters.items():
        if len(member_indices) == 1:
            lead = clean_candidates[member_indices[0]]
            lead["duplicate_cluster_id"] = None
            winner_leads.append(lead)
        else:
            # Sort cluster members: highest completeness score wins
            member_indices = sorted(member_indices, key=lambda i: score_lead_completeness(clean_candidates[i]),
                                    reverse=True)
            winner_idx = member_indices[0]
            winner = clean_candidates[winner_idx]
            cluster_id = f"CLUSTER-{run_id[:8]}-{winner.get('row_index', 0)}"
            winner["duplicate_cluster_id"] = cluster_id
            winner_leads.append(winner)

            members = set(member_indices)
            for dup_idx in member_indices[1:]:
                dup = clean_candidates[dup_idx]
                duplicate_records_merged += 1
                # The edge that linked this record into the cluster (direct to winner if one exists)
                direct = edges.get((min(winner_idx, dup_idx), max(winner_idx, dup_idx)))
                if direct:
                    sim_score, reason = direct
                else:
                    linked = [(pair, info) for pair, info in edges.items() if dup_idx in pair
                              and (pair[0] in members and pair[1] in members)]
                    sim_score, reason = linked[0][1] if linked else (0.0, "Linked through another cluster member")
                    reason = f"{reason} (linked via another record in the same cluster)"

                merged_logs.append({
                    "run_id": run_id,
                    "winner_raw_lead_id": winner.get("row_index", 0),
                    "archived_raw_lead_id": dup.get("row_index", 0),
                    "id_type": "csv_row",
                    "archived_lead_name": f"{dup.get('first_name') or ''} {dup.get('last_name') or ''}".strip(),
                    "archived_company": dup.get("company"),
                    "archived_email": dup.get("email"),
                    "similarity_score": sim_score,
                    "merge_reason": f"{reason}. Merged into CSV row #{winner.get('row_index', 0)}."
                })

    # Append junk leads as unmerged singletons
    for junk in junk_leads:
        junk["duplicate_cluster_id"] = None
        winner_leads.append(junk)

    # Keep a borderline pair only if both records are still separate cluster winners
    winner_ids = {id(l) for l in winner_leads}
    review_pairs = []
    seen_pairs = set()
    for i_idx, j_idx, sim, reason in review_candidates:
        a, b = clean_candidates[i_idx], clean_candidates[j_idx]
        key = (min(i_idx, j_idx), max(i_idx, j_idx))
        if key in seen_pairs or find(i_idx) == find(j_idx) or id(a) not in winner_ids or id(b) not in winner_ids:
            continue
        seen_pairs.add(key)
        review_pairs.append({
            "a_row": a.get("row_index", 0), "b_row": b.get("row_index", 0),
            "a": a, "b": b, "similarity_score": sim,
            "reason": f"Borderline fuzzy match ({REVIEW_BAND[0]:.0f}-{REVIEW_BAND[1]:.0f}% band): {reason}",
        })

    dedup_stats = {
        "review_pairs": review_pairs,
        "total_clusters": len(clusters) + len(junk_leads),
        "duplicate_clusters": sum(1 for m in clusters.values() if len(m) > 1),
        "duplicates_merged": duplicate_records_merged,
        "clean_winners_count": len(winner_leads)
    }

    return winner_leads, merged_logs, dedup_stats
