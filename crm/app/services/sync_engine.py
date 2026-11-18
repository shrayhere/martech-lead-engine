"""CSV synchronisation engine.

The same code path runs for a dry run (preview) and a real import; a dry run simply rolls the
transaction back at the end, so the preview always matches what an import would do.
A real import runs in one transaction: either every change is committed or none is.
"""
import csv
import json
import os
import time
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Company, Contact, DuplicateRecord, ImportJob, LeadActivity, SyncLog
from app.models.base import utcnow
from app.services import crm, csv_processor, lead_scoring
from app.services.data_cleaner import company_key
from app.services.duplicate_detector import ContactIndex, incoming_json
from app.utils.api import ApiError, audit

MODES = ("insert_only", "update_existing", "upsert")
CONTACT_UPDATE_FIELDS = ("first_name", "last_name", "email", "phone", "job_title", "lead_source", "lifecycle_stage")
COMPANY_UPDATE_FIELDS = ("industry", "website", "company_email", "phone", "address", "city", "country",
                         "employee_count", "annual_revenue", "description")
PREVIEW_ROW_LIMIT = 300
STALE_PROCESSING = timedelta(minutes=30)


def job_file_path(job):
    return os.path.join(current_app.config["UPLOAD_FOLDER"], str(job.user_id), job.stored_filename)


def load_job_text(job):
    path = job_file_path(job)
    if not os.path.exists(path):
        raise ApiError("The uploaded file is no longer available. Please upload it again.", 410)
    with open(path, "rb") as fh:
        data = fh.read()
    text, _, _ = csv_processor.decode(data)
    return text


class _Run:
    def __init__(self, job, mode, mapping, dry_run):
        self.job, self.mode, self.mapping, self.dry_run = job, mode, mapping, dry_run
        self.owner_id = job.user_id
        self.counts = dict(total=0, inserted=0, updated=0, unchanged=0, skipped=0, duplicates=0,
                           review=0, failed=0, companies_created=0, companies_updated=0, activities_added=0,
                           warnings=0)
        self.rows, self.failed_rows, self.duplicate_rows, self.success_rows = [], [], [], []
        self.touched = {}
        self.seen_emails = {}
        self.cc = current_app.config.get("DEFAULT_COUNTRY_CODE", "+1")
        self.now = utcnow()

    # ------------------------------------------------------------------ helpers
    def outcome(self, row_number, action, cleaned=None, reason=None, contact=None, changes=None, warnings=None):
        c = (cleaned or {}).get("contact") or {}
        company = (cleaned or {}).get("company") or {}
        entry = {
            "row": row_number, "action": action, "reason": reason,
            "name": " ".join(p for p in (c.get("first_name"), c.get("last_name")) if p) or None,
            "email": c.get("email"), "phone": c.get("phone"), "company": company.get("company_name"),
            "contact_id": contact.contact_id if contact is not None else None,
            "changes": changes or [], "warnings": warnings or [],
        }
        if len(self.rows) < PREVIEW_ROW_LIMIT:
            self.rows.append(entry)
        return entry

    def company_for(self, payload):
        if not payload:
            return None
        key = company_key(payload["company_name"])
        company = self.companies.get(key)
        if company is None:
            fields = {k: v for k, v in payload.items() if k in Company.EDITABLE_FIELDS}
            company = Company(owner_id=self.owner_id, name_key=key, **fields)
            db.session.add(company)
            self.companies[key] = company
            self.counts["companies_created"] += 1
        elif self.mode != "insert_only" and company.company_id is not None:
            changed = False
            for f in COMPANY_UPDATE_FIELDS:
                new = payload.get(f)
                if new not in (None, "") and getattr(company, f) != new:
                    if f == "annual_revenue" and company.annual_revenue is not None and \
                            float(company.annual_revenue) == float(new):
                        continue
                    setattr(company, f, new)
                    changed = True
            if changed and key not in self.updated_companies:
                self.updated_companies.add(key)
                self.counts["companies_updated"] += 1
        return company

    def add_activity(self, contact, activity):
        if not activity:
            return False
        contact.activities.append(LeadActivity(
            activity_type=activity["activity_type"], activity_description=activity.get("activity_description"),
            activity_date=activity["activity_date"]))
        self.counts["activities_added"] += 1
        return True

    def mark_touched(self, contact):
        self.touched[id(contact)] = contact

    # ------------------------------------------------------------------ row handling
    def handle_row(self, row_number, raw, parse_error):
        self.counts["total"] += 1
        if parse_error:
            return self.fail(row_number, raw, [parse_error])
        cleaned = csv_processor.clean_record(raw, self.mapping, self.cc, self.now)
        if cleaned["errors"]:
            return self.fail(row_number, raw, cleaned["errors"], cleaned)
        warnings = cleaned["warnings"]
        self.counts["warnings"] += len(warnings)
        c = cleaned["contact"]
        email = c.get("email")
        ckey = company_key((cleaned["company"] or {}).get("company_name"))

        # Repeated email inside the same file: fold into the first occurrence.
        if email and email in self.seen_emails:
            first_contact, first_row = self.seen_emails[email]
            if first_contact is not None:
                for f in CONTACT_UPDATE_FIELDS:
                    if getattr(first_contact, f) in (None, "") and c.get(f):
                        setattr(first_contact, f, c[f])
                self.add_activity(first_contact, cleaned["activity"])
                self.mark_touched(first_contact)
            reason = f"Repeated email in this file (first seen on row {first_row}); details combined."
            return self.duplicate(row_number, cleaned, reason, 1.0, first_contact, "merged_in_file", warnings)

        match = self.index.match(email, c.get("phone"), c.get("first_name"), c.get("last_name"), ckey)

        if match and match.certain:
            existing = db.session.get(Contact, match.contact_id)
            self.seen_emails[email] = (existing, row_number)
            if self.mode == "insert_only":
                return self.duplicate(row_number, cleaned, "Email already exists; skipped in insert-only mode.",
                                      1.0, existing, "skipped_existing", warnings)
            return self.update_existing(row_number, existing, cleaned, warnings)

        if match:
            existing = db.session.get(Contact, match.contact_id)
            dup = DuplicateRecord(owner_id=self.owner_id, original_contact_id=match.contact_id,
                                  import_id=self.job.import_id, incoming_data=incoming_json(cleaned, row_number),
                                  matching_reason=match.reason, confidence_score=match.confidence)
            db.session.add(dup)
            self.counts["review"] += 1
            if email:
                self.seen_emails[email] = (None, row_number)
            return self.duplicate(row_number, cleaned, f"{match.reason} — needs review before merging.",
                                  match.confidence, existing, "pending_review", warnings)

        if self.mode == "update_existing":
            self.counts["skipped"] += 1
            self.outcome(row_number, "skipped", cleaned, "No matching contact; update-only mode does not insert.",
                         warnings=warnings)
            return
        return self.insert(row_number, cleaned, warnings)

    def fail(self, row_number, raw, reasons, cleaned=None):
        self.counts["failed"] += 1
        self.failed_rows.append((row_number, reasons, raw))
        self.outcome(row_number, "failed", cleaned, "; ".join(reasons))

    def duplicate(self, row_number, cleaned, reason, confidence, existing, status, warnings):
        self.counts["duplicates"] += 1
        c = cleaned["contact"]
        self.duplicate_rows.append({
            "row": row_number, "status": status, "reason": reason, "confidence": confidence,
            "existing_contact_id": existing.contact_id if existing is not None else "",
            "existing_name": existing.full_name if existing is not None else "",
            "existing_email": existing.email if existing is not None else "",
            "incoming_name": " ".join(p for p in (c.get("first_name"), c.get("last_name")) if p),
            "incoming_email": c.get("email") or "", "incoming_phone": c.get("phone") or "",
        })
        self.outcome(row_number, "review" if status == "pending_review" else "duplicate", cleaned, reason,
                     existing, warnings=warnings)

    def insert(self, row_number, cleaned, warnings):
        c = dict(cleaned["contact"])
        c["lifecycle_stage"] = c.get("lifecycle_stage") or "lead"
        c["lead_source"] = c.get("lead_source") or "CSV Import"
        company = self.company_for(cleaned["company"])
        contact = Contact(owner_id=self.owner_id, **c)
        if company is not None:
            contact.company = company
        db.session.add(contact)
        contact.sources.append(self.source)
        self.add_activity(contact, cleaned["activity"])
        self.mark_touched(contact)
        if c.get("email"):
            self.seen_emails[c["email"]] = (contact, row_number)
        self.pending_index.append((contact, cleaned))
        self.counts["inserted"] += 1
        entry = self.outcome(row_number, "inserted", cleaned, None, contact, warnings=warnings)
        self.success_rows.append(("inserted", row_number, contact, cleaned, [], warnings, entry))

    def update_existing(self, row_number, contact, cleaned, warnings):
        before = contact.snapshot()
        changes = []
        for f in CONTACT_UPDATE_FIELDS:
            new = cleaned["contact"].get(f)
            if new not in (None, "") and getattr(contact, f) != new:
                setattr(contact, f, new)
                changes.append(f)
        company = self.company_for(cleaned["company"])
        if company is not None and contact.company is not company:
            contact.company = company
            changes.append("company")
        if self.add_activity(contact, cleaned["activity"]):
            changes.append("activity")
        crm.link_source(contact, self.source)
        if changes:
            self.mark_touched(contact)
            self.counts["updated"] += 1
            self.audit_updates.append((contact, before))
            entry = self.outcome(row_number, "updated", cleaned, None, contact, changes, warnings)
            self.success_rows.append(("updated", row_number, contact, cleaned, changes, warnings, entry))
        else:
            self.counts["unchanged"] += 1
            self.counts["skipped"] += 1
            self.outcome(row_number, "unchanged", cleaned, "Already up to date; no changes.", contact,
                         warnings=warnings)

    # ------------------------------------------------------------------ main
    def execute(self, text, columns):
        self.index = ContactIndex(self.owner_id)
        self.companies = {c.name_key: c for c in Company.query.filter_by(owner_id=self.owner_id)}
        self.updated_companies = set()
        self.source = crm.get_source(self.owner_id, "CSV Import", "csv",
                                     "Contacts created or updated through CSV synchronisation.")
        self.audit_updates = []
        chunk_size = current_app.config.get("CSV_CHUNK_SIZE", 1000)
        for chunk in csv_processor.iter_chunks(text, self.job.delimiter or ",", columns, chunk_size):
            self.pending_index = []
            for row_number, raw, err in chunk:
                self.handle_row(row_number, raw, err)
            db.session.flush()  # bulk write of this chunk; assigns primary keys
            for contact, cleaned in self.pending_index:
                ckey = company_key((cleaned["company"] or {}).get("company_name"))
                self.index.add(contact.contact_id, contact.email, contact.phone, contact.first_name,
                               contact.last_name, ckey)
        db.session.flush()
        lead_scoring.recalculate_contacts(list(self.touched.values()), self.owner_id, self.now)
        if not self.dry_run:
            for contact, before in self.audit_updates:
                after = contact.snapshot()
                old = {k: v for k, v in before.items() if after.get(k) != v}
                new = {k: after[k] for k in old}
                audit("contact", contact.contact_id, "import_update", old, new, user_id=self.owner_id)
        for entry_tuple in self.success_rows:
            entry_tuple[6]["contact_id"] = entry_tuple[2].contact_id
            entry_tuple[6]["lead_score"] = entry_tuple[2].lead_score
            entry_tuple[6]["lead_category"] = entry_tuple[2].effective_category


def _write_reports(job, run, columns):
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "reports")
    os.makedirs(folder, exist_ok=True)
    paths = {}
    if run.failed_rows:
        path = os.path.join(folder, f"import_{job.import_id}_failed.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["row_number", "errors"] + columns)
            for row_number, reasons, raw in run.failed_rows:
                w.writerow([row_number, "; ".join(reasons)] + [(raw or {}).get(c, "") for c in columns])
        paths["error"] = path
    if run.duplicate_rows:
        path = os.path.join(folder, f"import_{job.import_id}_duplicates.csv")
        keys = ["row", "status", "reason", "confidence", "existing_contact_id", "existing_name", "existing_email",
                "incoming_name", "incoming_email", "incoming_phone"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(run.duplicate_rows)
        paths["duplicate"] = path
    path = os.path.join(folder, f"import_{job.import_id}_success.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row_number", "action", "contact_id", "first_name", "last_name", "email", "phone", "company",
                    "lead_score", "lead_category", "changed_fields", "warnings"])
        for action, row_number, contact, cleaned, changes, warnings, _ in run.success_rows:
            w.writerow([row_number, action, contact.contact_id, contact.first_name, contact.last_name or "",
                        contact.email or "", contact.phone or "",
                        contact.company.company_name if contact.company else "", contact.lead_score,
                        contact.effective_category or "excluded", ", ".join(changes), " | ".join(warnings)])
    paths["success"] = path
    return paths


def _check_concurrency(job):
    busy = ImportJob.query.filter(
        ImportJob.user_id == job.user_id, ImportJob.import_status == "processing",
        ImportJob.import_id != job.import_id, ImportJob.started_at > utcnow() - STALE_PROCESSING,
    ).with_for_update().first()
    if busy:
        raise ApiError(f"Another import ('{busy.original_filename}') is still running. "
                       "Please wait for it to finish.", 409)


def run_sync(job, mapping, mode, dry_run=False):
    if mode not in MODES:
        raise ApiError("Sync mode must be insert_only, update_existing or upsert.", 400)
    if job.import_status in ("completed", "processing", "rolled_back") and not dry_run:
        raise ApiError(f"This import is already {job.import_status.replace('_', ' ')}. Upload the file again "
                       "to run another synchronisation.", 409)
    text = load_job_text(job)
    columns = csv_processor.read_header(text, job.delimiter or ",")
    clean_mapping = csv_processor.validate_mapping(mapping, columns)
    job_id = job.import_id

    started = time.perf_counter()
    if not dry_run:
        _check_concurrency(job)
        job.import_status = "processing"
        job.sync_mode = mode
        job.column_mapping = json.dumps(mapping)
        job.started_at = utcnow()
        db.session.commit()

    run = _Run(job, mode, clean_mapping, dry_run)
    try:
        run.execute(text, columns)
        if dry_run:
            db.session.rollback()
        else:
            paths = _write_reports(job, run, columns)
            duration = int((time.perf_counter() - started) * 1000)
            log = SyncLog(import_id=job.import_id, source_id=run.source.source_id, sync_type=mode,
                          records_inserted=run.counts["inserted"], records_updated=run.counts["updated"],
                          records_skipped=run.counts["skipped"] + run.counts["duplicates"],
                          records_failed=run.counts["failed"], sync_status="completed",
                          started_at=job.started_at, completed_at=utcnow())
            db.session.add(log)
            job.total_rows = run.counts["total"]
            job.inserted_rows = run.counts["inserted"]
            job.updated_rows = run.counts["updated"]
            job.successful_rows = run.counts["inserted"] + run.counts["updated"]
            job.failed_rows = run.counts["failed"]
            job.duplicate_rows = run.counts["duplicates"]
            job.skipped_rows = run.counts["skipped"]
            job.error_report_path = paths.get("error")
            job.duplicate_report_path = paths.get("duplicate")
            job.success_report_path = paths.get("success")
            job.import_status = "completed"
            job.completed_at = utcnow()
            job.duration_ms = duration
            audit("import", job.import_id, "execute", None,
                  {"mode": mode, **{k: v for k, v in run.counts.items()}}, user_id=job.user_id)
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        if dry_run:
            raise
        job = db.session.get(ImportJob, job_id)
        job.import_status = "rolled_back"
        if isinstance(exc, IntegrityError):
            job.error_message = ("Another operation changed the same records at the same time. "
                                 "The import was rolled back; no changes were saved. Please retry.")
        elif isinstance(exc, ApiError):
            job.error_message = exc.message
        else:
            current_app.logger.exception("Import %s failed", job_id)
            job.error_message = f"Import failed and was rolled back; no changes were saved. ({type(exc).__name__})"
        job.completed_at = utcnow()
        db.session.add(SyncLog(import_id=job.import_id, sync_type=mode, sync_status="rolled_back",
                               started_at=job.started_at or utcnow(), completed_at=utcnow(),
                               records_failed=run.counts["total"]))
        db.session.commit()
        raise ApiError(job.error_message, 409 if isinstance(exc, IntegrityError) else 500)

    duration = int((time.perf_counter() - started) * 1000)
    if dry_run:
        job = db.session.get(ImportJob, job_id)
        if job.import_status == "uploaded":
            job.import_status = "previewed"
        job.column_mapping = json.dumps(mapping)
        job.sync_mode = mode
        db.session.commit()
    counts = run.counts
    return {
        "import_id": job_id,
        "dry_run": dry_run,
        "mode": mode,
        "summary": {
            "total_processed": counts["total"],
            "inserted": counts["inserted"],
            "updated": counts["updated"],
            "unchanged": counts["unchanged"],
            "duplicates": counts["duplicates"],
            "needs_review": counts["review"],
            "skipped": counts["skipped"],
            "invalid": counts["failed"],
            "failed": counts["failed"],
            "companies_created": counts["companies_created"],
            "companies_updated": counts["companies_updated"],
            "activities_added": counts["activities_added"],
            "warnings": counts["warnings"],
            "duration_ms": duration,
        },
        "rows": run.rows,
        "rows_truncated": counts["total"] > len(run.rows),
        "job": db.session.get(ImportJob, job_id).to_dict(),
    }
