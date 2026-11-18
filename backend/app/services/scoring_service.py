import json
import math
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.schemas import CleanLead
from app.config import settings
from app.ml.scoring_model import ml_scorer

def _has_keyword(title: str, keywords) -> bool:
    """Whole-word match: plain substring matching found "cto" inside "director", so every
    Director was scored as C-level."""
    return any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", title) for k in keywords)


def classify_seniority(job_title: str) -> tuple[int, str]:
    """Classifies job title into seniority tier score and human label."""
    if not job_title:
        return 25, "Individual Contributor"

    t = job_title.lower()
    # "Vice President" is VP tier, not "President"
    if _has_keyword(t.replace("vice president", "vp"), settings.C_LEVEL_KEYWORDS):
        return 100, "C-Level / Founder"
    elif _has_keyword(t, settings.VP_DIRECTOR_KEYWORDS):
        return 80, "VP / Director"
    elif _has_keyword(t, settings.MANAGER_KEYWORDS):
        return 50, "Manager / Sr Lead"
    return 25, "Staff / Contributor"

def score_company_size(size: int) -> tuple[int, str]:
    """Maps company size integer to 0-100 firmographic score and size bucket label."""
    if not size or size <= 0:
        return 35, "< 50 employees"
    if size >= 5000:
        return 100, "Enterprise (5,000+)"
    elif size >= 1000:
        return 85, "Upper Mid-Market (1,000-4,999)"
    elif size >= 100:
        return 65, "Mid-Market (100-999)"
    elif size >= 50:
        return 50, "Small Business (50-99)"
    return 35, "Micro Business (< 50)"

def score_recency(activity_date_str: str) -> tuple[float, int]:
    """Applies exponential decay scoring to recency of last activity date."""
    if not activity_date_str:
        return 30.0, 90

    try:
        act_date = datetime.strptime(activity_date_str[:10], "%Y-%m-%d")
        days = (datetime.now() - act_date).days
        days = max(0, min(180, days))
    except Exception:
        return 30.0, 90

    # Exponential decay formula: score = 100 * exp(-0.02 * days)
    decay_score = 100.0 * math.exp(-0.02 * days)
    return round(decay_score, 1), days

def calculate_rule_based_score(lead) -> tuple[float, dict]:
    """
    Computes explainable weighted score (0-100) combining:
    - Firmographic signals (40% total): company size (15%), target industry (15%), title seniority (10%).
    - Behavioral signals (60% total): engagement score (35%), recency decay (25%).
    Returns final score and detailed signal contribution breakdown dictionary.
    """
    # 1. Firmographic: Company Size
    size_raw = lead.company_size or 0
    size_score, size_label = score_company_size(size_raw)
    size_points = round(size_score * settings.WEIGHT_COMPANY_SIZE, 1)

    # 2. Firmographic: Target Industry
    ind_raw = lead.industry or ""
    is_target_ind = any(t.lower() in ind_raw.lower() for t in settings.TARGET_INDUSTRIES)
    ind_score = 100 if is_target_ind else 30
    ind_points = round(ind_score * settings.WEIGHT_TARGET_INDUSTRY, 1)

    # 3. Firmographic: Title Seniority
    title_raw = lead.job_title or ""
    sen_score, sen_label = classify_seniority(title_raw)
    sen_points = round(sen_score * settings.WEIGHT_TITLE_SENIORITY, 1)

    # 4. Behavioral: Engagement Score
    eng_score = float(lead.engagement_score or 0.0)
    eng_points = round(eng_score * settings.WEIGHT_ENGAGEMENT, 1)

    # 5. Behavioral: Recency Decay
    rec_score, days_ago = score_recency(lead.last_activity_date)
    rec_points = round(rec_score * settings.WEIGHT_RECENCY, 1)

    # Total score calculation
    total_score = round(size_points + ind_points + sen_points + eng_points + rec_points, 1)
    total_score = min(100.0, max(0.0, total_score))

    breakdown = {
        "final_rule_score": total_score,
        "firmographic_total": round(size_points + ind_points + sen_points, 1),
        "behavioral_total": round(eng_points + rec_points, 1),
        "signals": [
            {
                "name": "Company Size",
                "category": "Firmographic",
                "raw_value": f"{size_raw} employees ({size_label})",
                "signal_score": size_score,
                "weight": settings.WEIGHT_COMPANY_SIZE,
                "points_contributed": size_points,
                "explanation": f"Company size {size_label} grants {size_score}/100 raw points (weighted {int(settings.WEIGHT_COMPANY_SIZE*100)}%)."
            },
            {
                "name": "Industry Match",
                "category": "Firmographic",
                "raw_value": ind_raw or "Unspecified",
                "signal_score": ind_score,
                "weight": settings.WEIGHT_TARGET_INDUSTRY,
                "points_contributed": ind_points,
                "explanation": "Target high-value industry match" if is_target_ind else "Non-target market segment"
            },
            {
                "name": "Job Seniority",
                "category": "Firmographic",
                "raw_value": f"{title_raw} ({sen_label})",
                "signal_score": sen_score,
                "weight": settings.WEIGHT_TITLE_SENIORITY,
                "points_contributed": sen_points,
                "explanation": f"Seniority level classified as {sen_label}"
            },
            {
                "name": "Engagement Score",
                "category": "Behavioral",
                "raw_value": f"{eng_score:.0f} / 100",
                "signal_score": eng_score,
                "weight": settings.WEIGHT_ENGAGEMENT,
                "points_contributed": eng_points,
                "explanation": f"Recorded marketing engagement score (emails/clicks) weighted at {int(settings.WEIGHT_ENGAGEMENT*100)}%"
            },
            {
                "name": "Activity Recency",
                "category": "Behavioral",
                "raw_value": f"{days_ago} days ago ({lead.last_activity_date or 'N/A'})",
                "signal_score": rec_score,
                "weight": settings.WEIGHT_RECENCY,
                "points_contributed": rec_points,
                "explanation": f"Exponential decay score based on {days_ago} days elapsed recency"
            }
        ]
    }

    return total_score, breakdown

def assign_score_band(score: float) -> str:
    """Classifies numerical score 0-100 into Hot (80-100), Warm (50-79), Cold (0-49)."""
    if score >= 80.0:
        return "Hot"
    elif score >= 50.0:
        return "Warm"
    return "Cold"

def run_lead_scoring(db: Session, scoring_mode: str = "rule") -> dict:
    """
    Scores all clean, non-junk leads in the database using either:
    - 'rule': Rule-based weighted explainable scoring
    - 'ml': Scikit-Learn Logistic Regression model
    Updates rule_score, ml_score, active_score, score_band, and score_breakdown on clean_leads.
    """
    leads = db.query(CleanLead).filter(CleanLead.is_junk == False, CleanLead.run_id.is_(None)).all()
    if not leads:
        return {"error": "No clean leads available for scoring. Please run Data Quality stage first."}

    scored_count = 0
    hot_count = 0
    warm_count = 0
    cold_count = 0

    for lead in leads:
        # 1. Rule-based score & breakdown
        rule_score, breakdown = calculate_rule_based_score(lead)
        
        # 2. ML model score
        ml_score = ml_scorer.predict_score(lead)

        # 3. Determine active score based on chosen mode
        active = rule_score if scoring_mode == "rule" else ml_score
        band = assign_score_band(active)

        lead.rule_score = rule_score
        lead.ml_score = ml_score
        lead.active_score = active
        lead.score_band = band
        lead.score_breakdown = json.dumps(breakdown)

        scored_count += 1
        if band == "Hot":
            hot_count += 1
        elif band == "Warm":
            warm_count += 1
        else:
            cold_count += 1

    db.commit()

    return {
        "success": True,
        "scoring_mode_applied": scoring_mode,
        "total_leads_scored": scored_count,
        "distribution": {
            "Hot": hot_count,
            "Warm": warm_count,
            "Cold": cold_count
        }
    }
