"""Lead scoring engine.

score = sum(points of engagement activities, using the owner's configurable rules)
        + inactivity penalty (once) when there has been no engagement for INACTIVITY_DAYS
          or a "no recent engagement" activity was logged after the last engagement,
bounded to 0..100.

Category: hot 60-100, warm 30-59, cold 0-29. Contacts without a valid email or phone are
excluded from qualification (category NULL, status 'excluded').
"""
from collections import defaultdict
from datetime import timedelta

from app.extensions import db
from app.models import (DEFAULT_SCORING_RULES, INACTIVITY_DAYS, INACTIVITY_RULE, Contact, LeadActivity,
                        ScoringRule)
from app.models.base import utcnow
from app.services.data_cleaner import is_valid_email

HOT_MIN = 60
WARM_MIN = 30


def ensure_default_rules(owner_id):
    existing = {r.activity_type for r in ScoringRule.query.filter_by(owner_id=owner_id)}
    for activity_type, (label, points) in DEFAULT_SCORING_RULES.items():
        if activity_type not in existing:
            db.session.add(ScoringRule(owner_id=owner_id, activity_type=activity_type, label=label, points=points))
    db.session.flush()


def get_rules(owner_id):
    rules = {r.activity_type: r for r in ScoringRule.query.filter_by(owner_id=owner_id)}
    if len(rules) < len(DEFAULT_SCORING_RULES):
        ensure_default_rules(owner_id)
        rules = {r.activity_type: r for r in ScoringRule.query.filter_by(owner_id=owner_id)}
    return {k: r.points for k, r in rules.items()}, {k: r.label for k, r in rules.items()}


def category_for(score):
    if score >= HOT_MIN:
        return "hot"
    if score >= WARM_MIN:
        return "warm"
    return "cold"


def has_valid_phone(phone):
    if not phone or not phone.startswith("+"):
        return False
    digits = phone[1:]
    return digits.isdigit() and 8 <= len(digits) <= 15


def is_qualifiable(contact):
    return is_valid_email(contact.email) or has_valid_phone(contact.phone)


def compute_score(activities, points, now=None):
    """activities: iterable of (activity_type, activity_date). Returns (score, last_engagement, penalty_applied)."""
    now = now or utcnow()
    engagement = [(t, d) for t, d in activities if t != INACTIVITY_RULE]
    total = sum(points.get(t, 0) for t, _ in engagement)
    last = max((d for _, d in engagement), default=None)
    logged_inactive = any(t == INACTIVITY_RULE and (last is None or d >= last) for t, d in activities)
    inactive = last is None or (now - last) > timedelta(days=INACTIVITY_DAYS)
    penalty = bool(engagement or logged_inactive) and (inactive or logged_inactive)
    if penalty:
        total += points.get(INACTIVITY_RULE, 0)
    return max(0, min(100, total)), last, penalty


def recalculate_contacts(contacts, owner_id, now=None):
    """Recalculate scores for a list of (flushed) contacts with one activities query."""
    contacts = [c for c in contacts if c is not None]
    if not contacts:
        return
    points, _ = get_rules(owner_id)
    ids = [c.contact_id for c in contacts]
    by_contact = defaultdict(list)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        for act in LeadActivity.query.filter(LeadActivity.contact_id.in_(chunk)):
            expected = points.get(act.activity_type, 0)
            if act.activity_score != expected:
                act.activity_score = expected
            by_contact[act.contact_id].append((act.activity_type, act.activity_date))
    for contact in contacts:
        score, last, _ = compute_score(by_contact.get(contact.contact_id, []), points, now)
        contact.lead_score = score
        contact.last_activity_at = last
        if is_qualifiable(contact):
            contact.lead_category = category_for(score)
            if contact.lead_status == "excluded":
                contact.lead_status = "open"
        else:
            contact.lead_category = None
            contact.lead_status = "excluded"


def recalculate_contact(contact):
    db.session.flush()
    recalculate_contacts([contact], contact.owner_id)


def recalculate_owner(owner_id):
    q = Contact.query.filter_by(owner_id=owner_id).order_by(Contact.contact_id)
    last_id = 0
    while True:
        batch = q.filter(Contact.contact_id > last_id).limit(500).all()
        if not batch:
            break
        recalculate_contacts(batch, owner_id)
        last_id = batch[-1].contact_id


def score_breakdown(contact):
    points, labels = get_rules(contact.owner_id)
    acts = contact.activities.all()
    score, last, penalty = compute_score([(a.activity_type, a.activity_date) for a in acts], points)
    items = [{"label": labels.get(a.activity_type, a.activity_type), "points": points.get(a.activity_type, 0),
              "activity_type": a.activity_type}
             for a in acts if a.activity_type != INACTIVITY_RULE]
    if penalty:
        items.append({"label": labels.get(INACTIVITY_RULE, "No activity for 30 days"),
                      "points": points.get(INACTIVITY_RULE, 0), "activity_type": INACTIVITY_RULE})
    raw = sum(i["points"] for i in items)
    return {"items": items, "raw_total": raw, "score": score, "bounded": raw != score}


def recommended_next_action(contact, recent_types=None):
    recent_types = set(recent_types or [])
    cat = contact.effective_category
    if contact.lead_category is None:
        return "Fix contact details: add a valid email address or phone number so the lead can be qualified."
    if contact.lifecycle_stage == "customer":
        return "Existing customer: hand over to account management and look for expansion opportunities."
    if cat == "hot":
        if "demo_requested" in recent_types:
            return "Schedule the requested product demo within 24 hours."
        if "pricing_inquiry" in recent_types:
            return "Send a tailored pricing proposal and book a call with sales."
        if "meeting_scheduled" in recent_types:
            return "Prepare for the scheduled meeting and share an agenda."
        return "Call this lead today: assign to a sales rep for immediate follow-up."
    if cat == "warm":
        if "brochure_downloaded" in recent_types or "website_visit" in recent_types:
            return "Send a case study related to the content viewed and offer a demo."
        return "Enrol in a nurture sequence and follow up with a personalised email this week."
    if contact.last_activity_at is None:
        return "No engagement yet: add to an awareness campaign."
    return "Re-engage with a newsletter or re-activation campaign; review again in 30 days."
