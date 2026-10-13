from collections import defaultdict
from typing import List, Dict, Any, Tuple
from rapidfuzz import fuzz
from app.config import settings

GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "proton.me", "protonmail.com", "mail.com", "zoho.com"
}

def get_blocking_keys(lead: Dict[str, Any]) -> List[str]:
    """
    Computes blocking keys to partition candidates into small buckets for high-speed fuzzy comparison.
    """
    keys = []
    email = lead.get("email") or ""
    if "@" in email:
        domain = email.split("@")[-1].lower().strip()
        if domain and domain not in GENERIC_DOMAINS:
            keys.append(f"dom:{domain}")

    comp = (lead.get("company") or "").lower().strip()
    if comp:
        # First 3 alphanumeric chars of company
        comp_prefix = "".join(c for c in comp if c.isalnum())[:3]
        if comp_prefix:
            keys.append(f"comp:{comp_prefix}")

    # Fallback bucket if no domain or company
    if not keys:
        state = (lead.get("state") or "").upper().strip()
        keys.append(f"st:{state or 'UNK'}")

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
    exact_merge_reasons: Dict[Tuple[int, int], str] = {}

    for idx, lead in enumerate(clean_candidates):
        em = lead.get("email")
        if em:
            if em in email_to_idx:
                prev_idx = email_to_idx[em]
                union(prev_idx, idx)
                exact_merge_reasons[(prev_idx, idx)] = f"Exact match on email address ({em})"
            else:
                email_to_idx[em] = idx

        ph = lead.get("phone")
        if ph:
            if ph in phone_to_idx:
                prev_idx = phone_to_idx[ph]
                union(prev_idx, idx)
                exact_merge_reasons[(prev_idx, idx)] = f"Exact match on E.164 phone number ({ph})"
            else:
                phone_to_idx[ph] = idx

    # PASS 2: Blocking Buckets for RapidFuzz 85% Composite Matching
    bucket_map: Dict[str, List[int]] = defaultdict(list)
    for idx, lead in enumerate(clean_candidates):
        for b_key in get_blocking_keys(lead):
            bucket_map[b_key].append(idx)

    fuzzy_merge_info: Dict[Tuple[int, int], Tuple[float, str]] = {}

    # Precompute composite string per lead
    composite_strings = [
        f"{l.get('first_name') or ''} {l.get('last_name') or ''} | {l.get('company') or ''} | {l.get('email') or ''}".lower()
        for l in clean_candidates
    ]

    for b_key, indices in bucket_map.items():
        n_in_bucket = len(indices)
        if n_in_bucket <= 1:
            continue

        for i_pos in range(n_in_bucket):
            i_idx = indices[i_pos]
            root_i = find(i_idx)
            str_i = composite_strings[i_idx]

            for j_pos in range(i_pos + 1, n_in_bucket):
                j_idx = indices[j_pos]
                if find(j_idx) == root_i:
                    continue  # already in same cluster

                str_j = composite_strings[j_idx]
                sim = fuzz.token_sort_ratio(str_i, str_j)
                if sim >= threshold:
                    union(i_idx, j_idx)
                    fuzzy_merge_info[(i_idx, j_idx)] = (
                        round(float(sim), 1),
                        f"Fuzzy token_sort_ratio match ({sim:.1f}% >= {threshold}%) inside bucket '{b_key}'"
                    )

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
            member_leads = [clean_candidates[idx] for idx in member_indices]
            member_leads.sort(key=score_lead_completeness, reverse=True)
            winner = member_leads[0]
            cluster_id = f"CLUSTER-{run_id[:8]}-{winner.get('row_index', 0)}"
            winner["duplicate_cluster_id"] = cluster_id
            winner_leads.append(winner)

            # Secondary duplicates are archived in audit log
            for dup in member_leads[1:]:
                duplicate_records_merged += 1
                sim_score = 100.0
                reason = "Exact match on identifier"

                pair_key1 = (winner.get("row_index", 0), dup.get("row_index", 0))
                pair_key2 = (dup.get("row_index", 0), winner.get("row_index", 0))

                if pair_key1 in exact_merge_reasons or pair_key2 in exact_merge_reasons:
                    sim_score = 100.0
                    reason = exact_merge_reasons.get(pair_key1) or exact_merge_reasons.get(pair_key2)
                elif pair_key1 in fuzzy_merge_info or pair_key2 in fuzzy_merge_info:
                    info = fuzzy_merge_info.get(pair_key1) or fuzzy_merge_info.get(pair_key2)
                    sim_score, reason = info[0], info[1]
                else:
                    sim_score = threshold
                    reason = f"Composite fuzzy similarity ({threshold}%) cluster member"

                merged_logs.append({
                    "run_id": run_id,
                    "archived_raw_lead_id": dup.get("row_index", 0),
                    "archived_lead_name": f"{dup.get('first_name') or ''} {dup.get('last_name') or ''}".strip(),
                    "archived_company": dup.get("company"),
                    "archived_email": dup.get("email"),
                    "similarity_score": sim_score,
                    "merge_reason": f"{reason}. Merged into primary lead row #{winner.get('row_index', 0)}."
                })

    # Append junk leads as unmerged singletons
    for junk in junk_leads:
        junk["duplicate_cluster_id"] = None
        winner_leads.append(junk)

    dedup_stats = {
        "total_clusters": len(clusters) + len(junk_leads),
        "duplicate_clusters": sum(1 for m in clusters.values() if len(m) > 1),
        "duplicates_merged": duplicate_records_merged,
        "clean_winners_count": len(winner_leads)
    }

    return winner_leads, merged_logs, dedup_stats
