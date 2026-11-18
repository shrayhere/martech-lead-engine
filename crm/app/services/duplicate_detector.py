"""Duplicate detection (exact email = certain; phone / name+company = needs review) and resolution."""
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from app.extensions import db
from app.models import Company, Contact, DuplicateRecord, LeadActivity
from app.models.base import utcnow
from app.services import crm, lead_scoring
from app.services.data_cleaner import company_key, phone_key
from app.utils.api import ApiError, audit

MERGE_FIELDS = ("first_name", "last_name", "email", "phone", "job_title", "lead_source", "lifecycle_stage")
FUZZY_NAME_THRESHOLD = 0.88


def name_key(first, last):
    return re.sub(r"[^a-z0-9]", "", f"{first or ''}{last or ''}".lower()) or None


@dataclass
class Match:
    contact_id: int
    reason: str
    confidence: float
    certain: bool


class ContactIndex:
    """In-memory lookup of an owner's contacts, built with a single query."""

    def __init__(self, owner_id):
        self.by_email = {}
        self.by_phone = defaultdict(set)
        self.by_name_company = defaultdict(set)
        self.by_company = defaultdict(set)
        self.names = {}
        company_keys = dict(
            db.session.query(Company.company_id, Company.name_key).filter(Company.owner_id == owner_id).all())
        rows = db.session.query(Contact.contact_id, Contact.email, Contact.phone, Contact.first_name,
                                Contact.last_name, Contact.company_id).filter(Contact.owner_id == owner_id)
        for cid, email, phone, first, last, company_id in rows:
            self.add(cid, email, phone, first, last, company_keys.get(company_id))

    def add(self, contact_id, email, phone, first, last, ckey):
        if email:
            self.by_email[email] = contact_id
        pk = phone_key(phone)
        if pk:
            self.by_phone[pk].add(contact_id)
        nk = name_key(first, last)
        self.names[contact_id] = nk
        if nk and ckey:
            self.by_name_company[(nk, ckey)].add(contact_id)
            self.by_company[ckey].add(contact_id)

    def match(self, email, phone, first, last, ckey, exclude=None):
        if email and email in self.by_email and self.by_email[email] != exclude:
            return Match(self.by_email[email], "Exact email match", 1.0, True)
        nk = name_key(first, last)
        pk = phone_key(phone)
        phone_ids = (self.by_phone.get(pk) or set()) - {exclude} if pk else set()
        if phone_ids:
            for cid in phone_ids:
                if nk and self.names.get(cid) == nk:
                    return Match(cid, "Same phone number and name", 0.95, False)
            return Match(min(phone_ids), "Same phone number", 0.85, False)
        if nk and ckey:
            ids = (self.by_name_company.get((nk, ckey)) or set()) - {exclude}
            if ids:
                return Match(min(ids), "Same name at the same company", 0.8, False)
            for cid in self.by_company.get(ckey, ()):
                if cid == exclude or not self.names.get(cid):
                    continue
                ratio = SequenceMatcher(None, nk, self.names[cid]).ratio()
                if ratio >= FUZZY_NAME_THRESHOLD:
                    return Match(cid, f"Similar name ({int(ratio * 100)}%) at the same company", 0.7, False)
        return None


def _pair_exists(owner_id, a, b):
    return DuplicateRecord.query.filter(
        DuplicateRecord.owner_id == owner_id,
        ((DuplicateRecord.original_contact_id == a) & (DuplicateRecord.duplicate_contact_id == b)) |
        ((DuplicateRecord.original_contact_id == b) & (DuplicateRecord.duplicate_contact_id == a)),
    ).first() is not None


def scan_existing(owner_id):
    """Find likely duplicates among stored contacts. Never merges; creates pending review items."""
    company_keys = dict(
        db.session.query(Company.company_id, Company.name_key).filter(Company.owner_id == owner_id).all())
    rows = db.session.query(Contact.contact_id, Contact.phone, Contact.first_name, Contact.last_name,
                            Contact.company_id).filter(Contact.owner_id == owner_id).order_by(Contact.contact_id).all()
    found = {}
    by_phone, by_company = defaultdict(list), defaultdict(list)
    for cid, phone, first, last, company_id in rows:
        nk = name_key(first, last)
        pk = phone_key(phone)
        if pk:
            by_phone[pk].append((cid, nk))
        ck = company_keys.get(company_id)
        if ck and nk:
            by_company[ck].append((cid, nk))
    for members in by_phone.values():
        for i, (a, na) in enumerate(members):
            for b, nb in members[i + 1:]:
                found[(a, b)] = ("Same phone number and name", 0.95) if na and na == nb else ("Same phone number", 0.85)
    for members in by_company.values():
        for i, (a, na) in enumerate(members):
            for b, nb in members[i + 1:]:
                if (a, b) in found:
                    continue
                if na == nb:
                    found[(a, b)] = ("Same name at the same company", 0.8)
                else:
                    ratio = SequenceMatcher(None, na, nb).ratio()
                    if ratio >= FUZZY_NAME_THRESHOLD:
                        found[(a, b)] = (f"Similar name ({int(ratio * 100)}%) at the same company", 0.7)
    created = 0
    for (a, b), (reason, conf) in found.items():
        if _pair_exists(owner_id, a, b):
            continue
        db.session.add(DuplicateRecord(owner_id=owner_id, original_contact_id=a, duplicate_contact_id=b,
                                       matching_reason=reason, confidence_score=conf))
        created += 1
    db.session.flush()
    return created


# ---------------------------------------------------------------- review helpers

def _incoming_fields(dup):
    """Return (contact_fields, company_name, activity) for the duplicate side of a review item."""
    if dup.duplicate_contact_id:
        c = dup.duplicate_contact
        return ({f: getattr(c, f) for f in MERGE_FIELDS},
                c.company.company_name if c.company else None, None)
    payload = dup.incoming or {}
    company = payload.get("company") or {}
    return payload.get("contact", {}), company.get("company_name"), payload.get("activity")


def field_differences(dup):
    original = dup.original_contact
    incoming, incoming_company, _ = _incoming_fields(dup)
    rows = []
    for f in MERGE_FIELDS:
        a, b = getattr(original, f), incoming.get(f)
        rows.append({"field": f, "existing": a, "incoming": b,
                     "status": "same" if (a or None) == (b or None) else
                     ("fills_blank" if not a and b else ("missing_incoming" if a and not b else "conflict"))})
    a = original.company.company_name if original.company else None
    rows.append({"field": "company", "existing": a, "incoming": incoming_company,
                 "status": "same" if company_key(a) == company_key(incoming_company) else
                 ("fills_blank" if not a and incoming_company else
                  ("missing_incoming" if a and not incoming_company else "conflict"))})
    return rows


def recommend(dup, diffs=None):
    diffs = diffs or field_differences(dup)
    statuses = {d["status"] for d in diffs}
    if "conflict" in statuses:
        return ("update_existing", "Incoming record has newer, conflicting values.") if dup.confidence_score >= 0.9 \
            else ("merge", "Merge to keep existing values and add any missing details.")
    if "fills_blank" in statuses:
        return "merge", "Incoming record only adds missing details; merging is safe."
    return "keep_existing", "Incoming record adds no new information."


def serialize(dup):
    data = dup.to_dict()
    diffs = field_differences(dup)
    action, why = recommend(dup, diffs)
    incoming, incoming_company, activity = _incoming_fields(dup)
    data.update({
        "existing": dup.original_contact.to_dict(),
        "incoming": {**incoming, "company_name": incoming_company, "activity": activity,
                     "contact_id": dup.duplicate_contact_id,
                     "row_number": (dup.incoming or {}).get("row_number")},
        "differences": diffs,
        "recommended_action": action,
        "recommendation_reason": why,
    })
    return data


def _resolve_company(owner_id, company_payload):
    if not company_payload or not company_payload.get("company_name"):
        return None
    existing = crm.find_company_by_name(owner_id, company_payload["company_name"])
    if existing:
        return existing
    fields = {k: v for k, v in company_payload.items() if k in Company.EDITABLE_FIELDS}
    return crm.create_company(owner_id, fields)


def _apply(original, incoming, company, overwrite):
    for f in MERGE_FIELDS:
        new = incoming.get(f)
        if new in (None, ""):
            continue
        current = getattr(original, f)
        if overwrite or current in (None, ""):
            if f == "email" and new != current:
                crm.ensure_unique_email(original.owner_id, new, exclude_id=original.contact_id)
            setattr(original, f, new)
    if company is not None and (overwrite or original.company_id is None):
        original.company_id = company.company_id


def resolve(dup, action, user_id):
    if dup.resolution_status != "pending":
        raise ApiError("This duplicate has already been resolved.", 409)
    if action not in ("keep_existing", "update_existing", "merge", "not_duplicate"):
        raise ApiError("Action must be keep_existing, update_existing, merge or not_duplicate.", 400)
    original = dup.original_contact
    before = original.snapshot()
    owner_id = dup.owner_id
    result = {"action": action, "contact_id": original.contact_id}

    if dup.duplicate_contact_id:
        other = dup.duplicate_contact
        other_snapshot = other.snapshot()
        if action != "not_duplicate":
            if action in ("update_existing", "merge"):
                incoming = {f: getattr(other, f) for f in MERGE_FIELDS}
                other_email = other.email
                if other_email and other_email != original.email and (action == "update_existing" or not original.email):
                    other.email = None  # free the unique email before moving it
                    db.session.flush()
                _apply(original, {**incoming, "email": other_email}, other.company, action == "update_existing")
            LeadActivity.query.filter_by(contact_id=other.contact_id).update(
                {LeadActivity.contact_id: original.contact_id}, synchronize_session=False)
            for src in other.sources:
                crm.link_source(original, src)
            audit("contact", other.contact_id, "delete_duplicate", other_snapshot,
                  {"merged_into": original.contact_id, "action": action}, user_id=user_id)
            # Keep what the removed contact looked like on the review record itself.
            dup.incoming_data = json.dumps({
                "contact": {f: other_snapshot.get(f) for f in MERGE_FIELDS},
                "company": {"company_name": other.company.company_name} if other.company else None,
                "activity": None, "removed_contact_id": other.contact_id}, default=str)
            dup.duplicate_contact_id = None
            db.session.flush()
            db.session.delete(other)
            db.session.flush()
            db.session.expire(original, ["activities"])
            result["removed_contact_id"] = dup.duplicate_contact_id
    else:
        payload = dup.incoming or {}
        incoming = payload.get("contact", {})
        activity = payload.get("activity")
        if action in ("update_existing", "merge"):
            company = _resolve_company(owner_id, payload.get("company"))
            _apply(original, incoming, company, action == "update_existing")
            if activity:
                _add_activity(original.contact_id, activity)
        elif action == "not_duplicate":
            crm.ensure_unique_email(owner_id, incoming.get("email"))
            company = _resolve_company(owner_id, payload.get("company"))
            fields = {f: incoming.get(f) for f in MERGE_FIELDS}
            fields["lifecycle_stage"] = fields.get("lifecycle_stage") or "lead"
            new_contact = Contact(owner_id=owner_id, company_id=company.company_id if company else None, **fields)
            db.session.add(new_contact)
            db.session.flush()
            if dup.import_id:
                from app.models import SyncLog
                log = SyncLog.query.filter_by(import_id=dup.import_id).first()
                if log and log.source:
                    crm.link_source(new_contact, log.source)
            if activity:
                _add_activity(new_contact.contact_id, activity)
            lead_scoring.recalculate_contact(new_contact)
            audit("contact", new_contact.contact_id, "create_from_duplicate_review", None, new_contact.snapshot(),
                  user_id=user_id)
            result["created_contact_id"] = new_contact.contact_id

    lead_scoring.recalculate_contact(original)
    after = original.snapshot()
    if before != after:
        audit("contact", original.contact_id, f"duplicate_{action}", before, after, user_id=user_id)
    dup.resolution_status = {"keep_existing": "kept_existing", "update_existing": "updated_existing",
                             "merge": "merged", "not_duplicate": "not_duplicate"}[action]
    dup.resolved_at = utcnow()
    dup.resolved_by = user_id
    audit("duplicate", dup.duplicate_id, "resolve", {"status": "pending"}, {"status": dup.resolution_status},
          user_id=user_id)
    return result


def _add_activity(contact_id, activity):
    date = activity.get("activity_date")
    if isinstance(date, str):
        date = datetime.fromisoformat(date.replace("Z", ""))
    db.session.add(LeadActivity(contact_id=contact_id, activity_type=activity["activity_type"],
                                activity_description=activity.get("activity_description"),
                                activity_date=date or utcnow()))


def incoming_json(cleaned, row_number):
    def enc(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return str(obj)
    return json.dumps({"contact": cleaned["contact"], "company": cleaned["company"],
                       "activity": cleaned["activity"], "row_number": row_number}, default=enc)
