import json
import math
import re
from datetime import datetime
from typing import Any, Optional, Tuple, Dict, List
from sqlalchemy.orm import Session
from app.models.schemas import CleanLead
from app.config import settings
from app.ml.scoring_model import ml_scorer

def _has_keyword(title: str, keywords) -> bool:
    """Whole-word match: plain substring matching found "cto" inside "director", so every
    Director was scored as C-level."""
    return any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", title) for k in keywords)


def classify_seniority(job_title: str) -> tuple[int, str]:
    """
    Classifies job title into seniority tier score and human label.
    Rules:
      - Low/Staff (25 pts): "Founder's Office", Intern, Student, Retired, Assistant, Specialist, Contributor
      - C-Level/Founder (100 pts): Owner, Proprietor, Founder, Co-founder, MD, Managing Director, CXO (CEO, CTO, CFO, etc.), Partner, President
      - VP/Director/Head (80 pts): Director, Head of X, "Head - X", GM, General Manager, Purchase Head, Procurement Head, Sourcing Head, VP, Vice President
      - Manager/Sr Lead (50 pts): Manager, Purchase/Procurement/Sourcing Manager, Lead, Team Lead, Supervisor, Senior Manager
    """
    if not job_title or not str(job_title).strip():
        return 25, "Staff / Contributor"

    t = str(job_title).lower().strip()

    # 1. Low / Staff overrides (explicit staff roles that contain words like 'founder' or 'office')
    # "Founder's Office", "Intern", "Student", "Retired", "Assistant", "Junior"
    low_roles = [
        "founder's office", "founders office", "founder office", "intern", "internship",
        "student", "retired", "trainee", "entry level", "assistant"
    ]
    if any(re.search(r"\b" + re.escape(w) + r"\b", t) for w in low_roles):
        return 25, "Staff / Contributor"

    # 2. C-Level / Founder / High Seniority (100 pts)
    # Owner, Proprietor, Founder, Co-founder, MD, Managing Director, CXO, Partner, President, SVP, EVP
    c_level_patterns = [
        r"\bowner\b", r"\bproprietor\b", r"\bfounder\b", r"\bco-founder\b", r"\bcofounder\b",
        r"\bmanaging director\b", r"\bmd\b", r"\bcxo\b", r"\bceo\b", r"\bcto\b", r"\bcfo\b",
        r"\bcio\b", r"\bcmo\b", r"\bcro\b", r"\bcoo\b", r"\bciso\b", r"\bchief executive\b",
        r"\bchief\b", r"\bpartner\b", r"\bmanaging partner\b", r"\bsvp\b", r"\bevp\b"
    ]
    if "vice president" not in t and "vp" not in t.split() and any(re.search(pat, t) for pat in c_level_patterns):
        return 100, "C-Level / Founder"
    if re.search(r"\bpresident\b", t) and not re.search(r"\bvice president\b|\bvp\b", t):
        return 100, "C-Level / Founder"

    # 3. VP / Director / Head of X / GM / Procurement Head (80 pts)
    vp_dir_patterns = [
        r"\bvice president\b", r"\bvp\b", r"\bavp\b",
        r"\bdirector\b", r"\bhead of\b", r"\bhead\s*-\s*", r"\bgeneral manager\b", r"\bgm\b",
        r"\bprocurement head\b", r"\bsourcing head\b", r"\bpurchase head\b",
        r"\bhead\s+sourcing\b", r"\bhead\s+procurement\b"
    ]
    if any(re.search(pat, t) for pat in vp_dir_patterns):
        return 80, "VP / Director"

    # 4. Manager / Sr Lead / Purchase/Procurement/Sourcing Manager (50 pts)
    mgr_patterns = [
        r"\bmanager\b", r"\bpurchase manager\b", r"\bprocurement manager\b", r"\bsourcing manager\b",
        r"\blead\b", r"\bteam lead\b", r"\bsupervisor\b", r"\bsenior manager\b", r"\bsr manager\b",
        r"\bsenior\b", r"\bsr\.?\b"
    ]
    if any(re.search(pat, t) for pat in mgr_patterns):
        return 50, "Manager / Sr Lead"

    return 25, "Staff / Contributor"


def score_company_size(size: Any) -> tuple[int, str]:
    """Maps company size integer to 0-100 firmographic score and size bucket label."""
    if size is None:
        return 0, "Missing"
    try:
        s = int(size)
    except (ValueError, TypeError):
        return 0, "Invalid"

    if s <= 0:
        return 0, "Invalid (<= 0)"
    if s >= 5000:
        return 100, "Enterprise (5,000+)"
    elif s >= 1000:
        return 85, "Upper Mid-Market (1,000-4,999)"
    elif s >= 100:
        return 65, "Mid-Market (100-999)"
    elif s >= 50:
        return 50, "Small Business (50-99)"
    return 35, "Micro Business (< 50)"


def score_recency(activity_date_str: Any) -> tuple[float, int]:
    """Applies exponential decay scoring to recency of last activity date. Invalid/missing/future date = 0.0 pts."""
    if not activity_date_str or not str(activity_date_str).strip():
        return 0.0, 180

    try:
        act_date = datetime.strptime(str(activity_date_str)[:10], "%Y-%m-%d")
        # Reject future dates
        if act_date > datetime.now():
            return 0.0, 180
        days = (datetime.now() - act_date).days
        days = max(0, min(180, days))
    except Exception:
        # Impossible dates like 1999-13-45 score lowest recency
        return 0.0, 180

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
