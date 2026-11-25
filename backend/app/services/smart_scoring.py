import json
import math
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.services.scoring_service import classify_seniority, score_company_size, score_recency, assign_score_band
from app.ml.scoring_model import ml_scorer

DEFAULT_WEIGHTS = {
    "company_size": settings.WEIGHT_COMPANY_SIZE,        # 0.15
    "target_industry": settings.WEIGHT_TARGET_INDUSTRY,  # 0.15
    "title_seniority": settings.WEIGHT_TITLE_SENIORITY,  # 0.10
    "engagement": settings.WEIGHT_ENGAGEMENT,            # 0.35
    "recency": settings.WEIGHT_RECENCY                   # 0.25
}

def determine_signal_availability(leads: List[Dict[str, Any]]) -> Dict[str, bool]:
    """
    Checks if behavioral and firmographic signals have any valid non-default data across the leads batch.
    """
    if not leads:
        return {k: True for k in DEFAULT_WEIGHTS}

    has_eng = any(l.get("engagement_score") is not None for l in leads)
    has_rec = any(l.get("last_activity_date") is not None and str(l.get("last_activity_date")).strip() != "" for l in leads)
    has_cs = any(l.get("company_size") is not None and l.get("company_size") > 0 for l in leads)
    has_ind = any(bool(l.get("industry") and str(l.get("industry")).strip() not in {"", "General Business"}) for l in leads)
    has_title = any(bool(l.get("job_title") and str(l.get("job_title")).strip()) for l in leads)

    return {
        "company_size": has_cs,
        "target_industry": has_ind,
        "title_seniority": has_title,
        "engagement": has_eng,
        "recency": has_rec
    }

def calculate_renormalized_weights(signal_availability: Dict[str, bool]) -> Tuple[Dict[str, float], List[str]]:
    """
    Degrades gracefully: re-normalizes weights across available signals so total weight = 1.0.
    """
    available_sum = sum(DEFAULT_WEIGHTS[sig] for sig, is_avail in signal_availability.items() if is_avail)
    degraded_signals = [sig for sig, is_avail in signal_availability.items() if not is_avail]

    if available_sum <= 0:
        # Fallback equal weights
        n = len(DEFAULT_WEIGHTS)
        return {sig: round(1.0 / n, 4) for sig in DEFAULT_WEIGHTS}, degraded_signals

    renormalized = {}
    for sig, def_weight in DEFAULT_WEIGHTS.items():
        if signal_availability.get(sig, False):
            renormalized[sig] = round(def_weight / available_sum, 4)
        else:
            renormalized[sig] = 0.0

    return renormalized, degraded_signals

def score_lead_with_adaptive_weights(
    lead: Dict[str, Any],
    active_weights: Dict[str, float]
) -> Tuple[float, Dict[str, Any], List[str]]:
    """
    Computes explainable score using active re-normalized weights.
    Validates ranges:
      - Engagement: 0-100 (out-of-range or missing scores 0.0 pts)
      - Company Size: > 0 (<=0 or missing scores 0.0 pts)
      - Recency: real calendar dates <= today (invalid/future/missing scores 0.0 pts)
    Adds data completeness warnings and flags to score reasons.
    """
    completeness_warnings = []

    # 1. Company Size (must be > 0)
    cs_val = lead.get("company_size")
    size_score, size_label = score_company_size(cs_val)
    if size_score == 0:
        completeness_warnings.append("Company size missing or invalid")
    w_cs = active_weights.get("company_size", 0.0)
    cs_points = round(size_score * w_cs, 1)

    # 2. Target Industry
    ind_val = lead.get("industry") or ""
    is_target_ind = any(t.lower() in ind_val.lower() for t in settings.TARGET_INDUSTRIES) if ind_val else False
    ind_score = 100 if is_target_ind else (30 if ind_val else 0)
    w_ind = active_weights.get("target_industry", 0.0)
    ind_points = round(ind_score * w_ind, 1)

    # 3. Title Seniority
    title_val = lead.get("job_title") or ""
    sen_score, sen_label = classify_seniority(title_val)
    if not title_val or not str(title_val).strip():
        completeness_warnings.append("Job title missing")
    w_sen = active_weights.get("title_seniority", 0.0)
    sen_points = round(sen_score * w_sen, 1)

    # 4. Engagement Score (0-100; missing or out-of-range = 0 pts)
    eng_val = lead.get("engagement_score")
    eng_missing = False
    if eng_val is None or str(eng_val).strip() in {"", "None", "nan"}:
        eng_score = 0.0
        eng_missing = True
        completeness_warnings.append("Engagement missing")
    else:
        try:
            ev = float(eng_val)
            if 0.0 <= ev <= 100.0:
                eng_score = ev
            else:
                eng_score = 0.0
                eng_missing = True
                completeness_warnings.append("Engagement out of range (treated as missing)")
        except (ValueError, TypeError):
            eng_score = 0.0
            eng_missing = True
            completeness_warnings.append("Engagement invalid")
    w_eng = active_weights.get("engagement", 0.0)
    eng_points = round(eng_score * w_eng, 1)

    # 5. Recency Decay (missing or invalid/future date = lowest recency 0 pts)
    rec_val = lead.get("last_activity_date")
    rec_score, days_ago = score_recency(rec_val)
    if rec_score == 0.0:
        completeness_warnings.append("Last activity date missing or invalid")
    w_rec = active_weights.get("recency", 0.0)
    rec_points = round(rec_score * w_rec, 1)

    total_score = round(cs_points + ind_points + sen_points + eng_points + rec_points, 1)
    total_score = min(100.0, max(0.0, total_score))

    signals = [
        {
            "name": "Company Size",
            "category": "Firmographic",
            "score": size_score,
            "weight": w_cs,
            "points": cs_points,
            "reason": f"Company size: {size_label} ({cs_val or 0} employees)"
        },
        {
            "name": "Industry Match",
            "category": "Firmographic",
            "score": ind_score,
            "weight": w_ind,
            "points": ind_points,
            "reason": f"Target industry match: {ind_val}" if is_target_ind else f"General industry: {ind_val or 'Unspecified'}"
        },
        {
            "name": "Job Seniority",
            "category": "Firmographic",
            "score": sen_score,
            "weight": w_sen,
            "points": sen_points,
            "reason": f"Seniority tier: {sen_label} ({title_val or 'Unspecified'})"
        },
        {
            "name": "Engagement Score",
            "category": "Behavioral",
            "score": eng_score,
            "weight": w_eng,
            "points": eng_points,
            "reason": f"Marketing engagement level: {eng_score:.0f}/100" if not eng_missing else "Engagement missing (scored 0)"
        },
        {
            "name": "Activity Recency",
            "category": "Behavioral",
            "score": rec_score,
            "weight": w_rec,
            "points": rec_points,
            "reason": f"Last touch {days_ago} days ago ({rec_val or 'N/A'})" if rec_score > 0 else "Activity date missing or invalid (lowest recency 0 pts)"
        }
    ]

    # Sort signals by points contributed to get top reasons
    sorted_signals = sorted(signals, key=lambda s: s["points"], reverse=True)
    top_3_reasons = [s["reason"] for s in sorted_signals[:3] if s["points"] > 0]
    if completeness_warnings:
        top_3_reasons.append("Completeness notice: " + "; ".join(completeness_warnings))

    if len(top_3_reasons) < 3:
        top_3_reasons.extend([s["reason"] for s in sorted_signals if s["reason"] not in top_3_reasons][: 3 - len(top_3_reasons)])

    breakdown = {
        "final_score": total_score,
        "data_completeness": len(completeness_warnings) == 0,
        "completeness_warnings": completeness_warnings,
        "top_reasons": top_3_reasons[:3],
        "signals": signals
    }

    return total_score, breakdown, top_3_reasons

class _MockLeadForML:
    """Lightweight adapter for ml_scorer.predict_score."""
    def __init__(self, d: Dict[str, Any]):
        self.company_size = d.get("company_size")
        self.industry = d.get("industry")
        self.job_title = d.get("job_title")
        self.engagement_score = d.get("engagement_score")
        self.last_activity_date = d.get("last_activity_date")

def smart_score_leads(
    leads: List[Dict[str, Any]],
    scoring_mode: str = "rule",
    hubspot_rules: List[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Scores all clean leads with automatic graceful degradation:
    - Automatically re-normalizes signal weights if engagement or recency columns are missing.
    - Applies HubSpot workflow scoring rules (boosts/penalties from imported workflows).
    - Computes both Rule-based and ML classifier scores.
    - Classifies leads into Hot (80-100), Warm (50-79), Cold (0-49).
    """
    if hubspot_rules is None:
        hubspot_rules = []

    availability = determine_signal_availability(leads)
    active_weights, degraded_signals = calculate_renormalized_weights(availability)

    hot_count = 0
    warm_count = 0
    cold_count = 0

    scored_leads = []

    # Pre-extract features for vectorized batch ML scoring
    non_junk_indices = []
    features_list = []
    for idx, lead in enumerate(leads):
        if not lead.get("is_junk"):
            non_junk_indices.append(idx)
            features_list.append(ml_scorer.extract_features(_MockLeadForML(lead)))

    ml_scores_map = {}
    if features_list and ml_scorer.pipeline is not None:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                X_mat = np.array(features_list)
                probs = ml_scorer.pipeline.predict_proba(X_mat)[:, 1]
                for orig_idx, p in zip(non_junk_indices, probs):
                    ml_scores_map[orig_idx] = round(float(p * 100), 1)
        except Exception:
            pass

    from app.services.hubspot_import import apply_hubspot_rules_to_lead

    for idx, lead in enumerate(leads):
        if lead.get("is_junk"):
            lead["rule_score"] = 0.0
            lead["ml_score"] = 0.0
            lead["active_score"] = 0.0
            lead["score_band"] = "Cold"
            lead["score_breakdown"] = json.dumps({"reason": "Junk placeholder lead", "signals": []})
            cold_count += 1
            scored_leads.append(lead)
            continue

        rule_score, breakdown, top_reasons = score_lead_with_adaptive_weights(lead, active_weights)
        ml_score = ml_scores_map.get(idx, rule_score)

        # Apply HubSpot workflow-derived rules if available
        hs_delta = apply_hubspot_rules_to_lead(lead, hubspot_rules) if hubspot_rules else 0.0
        if hs_delta != 0.0:
            rule_score = min(100.0, max(0.0, rule_score + hs_delta))
            ml_score = min(100.0, max(0.0, ml_score + hs_delta))
            breakdown["hubspot_workflow_delta"] = hs_delta
            breakdown["signals"].append({
                "name": "HubSpot Workflow Rule",
                "category": "Automation",
                "score": hs_delta,
                "weight": 1.0,
                "points": hs_delta,
                "reason": f"Workflow score modifier: {hs_delta:+.1f} pts"
            })

        active_score = rule_score if scoring_mode == "rule" else ml_score

        # Part 5 Requirement: A lead with needs_review (e.g. phone but no valid email) goes to Review, never straight to Hot
        if lead.get("needs_review"):
            active_score = min(active_score, 74.9)  # Cap at Warm, never Hot

        band = assign_score_band(active_score)

        if band == "Hot":
            hot_count += 1
        elif band == "Warm":
            warm_count += 1
        else:
            cold_count += 1

        lead["rule_score"] = rule_score
        lead["ml_score"] = ml_score
        lead["active_score"] = active_score
        lead["score_band"] = band
        lead["score_breakdown"] = json.dumps(breakdown)

        scored_leads.append(lead)

    scoring_summary = {
        "scoring_mode": scoring_mode,
        "total_scored": len(scored_leads),
        "degraded_signals": degraded_signals,
        "re_normalized_weights": active_weights,
        "hubspot_rules_applied": len(hubspot_rules),
        "distribution": {
            "Hot": hot_count,
            "Warm": warm_count,
            "Cold": cold_count
        }
    }

    return scored_leads, scoring_summary
