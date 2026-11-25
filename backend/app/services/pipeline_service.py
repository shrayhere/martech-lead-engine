import time
import json
import uuid
import math
import gc
import logging
import tracemalloc
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def sanitize_for_json(obj: Any) -> Any:
    """Recursively replaces NaN and Inf floats with None for strict JSON compliance."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    return obj


from app.database import SessionLocal
from app.models.schemas import RawLead, CleanLead, MergedLeadLog, CleaningLog, AssignmentLog, PipelineRun, ReviewItem
from app.services.quality_service import quality_before_from_records
from app.services.classifier import label_lead_dicts


def _snapshot(rec: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("first_name", "last_name", "email", "company", "job_title", "phone", "state", "industry",
            "engagement_score", "junk_reason")
    return {k: rec.get(k) for k in keys}
from app.services.smart_parser import parse_csv_file
from app.services.schema_mapper import apply_schema_mapping
from app.services.pipeline_cleaning import clean_and_normalize_records
from app.services.fast_dedup import fast_deduplicate_leads
from app.services.smart_scoring import smart_score_leads
from app.services.smart_assignment import assign_leads_in_memory

# In-memory storage for uploaded file bytes to support mapping overrides without re-uploading
FILE_CACHE: Dict[str, bytes] = {}
RUN_PROGRESS: Dict[str, Dict[str, Any]] = {}

def update_run_progress(
    run_id: str,
    stage: str,
    progress_percent: int,
    status: str = "running",
    db: Optional[Session] = None
):
    """Updates in-memory and database progress state."""
    RUN_PROGRESS[run_id] = {
        "run_id": run_id,
        "status": status,
        "stage": stage,
        "progress_percent": progress_percent
    }
    if db:
        try:
            db.query(PipelineRun).filter(PipelineRun.run_id == run_id).update({
                PipelineRun.stage: stage,
                PipelineRun.progress_percent: progress_percent,
                PipelineRun.status: status
            })
            db.commit()
        except Exception:
            db.rollback()

def execute_smart_pipeline(
    file_bytes: bytes,
    filename: str,
    run_id: Optional[str] = None,
    mapping_override: Optional[Dict[str, str]] = None,
    scoring_mode: str = "rule",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Executes the One-Shot End-to-End Pipeline:
    1. Parse (smart_parser)
    2. Map (schema_mapper)
    3. Clean (pipeline_cleaning)
    4. Dedupe (fast_dedup)
    5. Score (smart_scoring)
    6. Assign (smart_assignment)
    7. Bulk Database Transaction & Timings
    """
    run_id = run_id or str(uuid.uuid4())
    FILE_CACHE[run_id] = file_bytes

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    total_start = time.perf_counter()
    timings = {}
    tracemalloc.start()

    def _get_peak_mb() -> float:
        try:
            _, peak = tracemalloc.get_traced_memory()
            return round(peak / (1024 * 1024), 2)
        except Exception:
            return 0.0

    # Initialize PipelineRun in DB
    existing_run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not existing_run:
        p_run = PipelineRun(
            run_id=run_id,
            filename=filename,
            status="running",
            stage="parse",
            progress_percent=5
        )
        db.add(p_run)
        db.commit()
    else:
        existing_run.status = "running"
        existing_run.stage = "parse"
        existing_run.progress_percent = 5
        db.commit()

    update_run_progress(run_id, "parse", 10, "running", db)

    try:
        # ----------------------------------------------------
        # STAGE 1: PARSE
        # ----------------------------------------------------
        t0 = time.perf_counter()
        raw_df, parse_meta = parse_csv_file(file_bytes, filename)
        rows_in = len(raw_df)
        timings["parse_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["parse_peak_mb"] = _get_peak_mb()
        logger.info("Pipeline %s [parse]: %.2f ms, peak: %.2f MB", run_id, timings["parse_ms"], timings["parse_peak_mb"])
        update_run_progress(run_id, "map", 25, "running", db)

        # ----------------------------------------------------
        # STAGE 2: SCHEMA ABSTRACTION & MAPPING
        # ----------------------------------------------------
        t0 = time.perf_counter()
        mapped_df, mapping_summary = apply_schema_mapping(raw_df, mapping_override)
        timings["map_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["map_peak_mb"] = _get_peak_mb()
        logger.info("Pipeline %s [map]: %.2f ms, peak: %.2f MB", run_id, timings["map_ms"], timings["map_peak_mb"])
        # Data-quality "before" snapshot (the raw file itself is not stored)
        quality_before = quality_before_from_records(
            mapped_df.astype(object).where(mapped_df.notna(), None).to_dict("records"))
        del raw_df
        gc.collect()
        update_run_progress(run_id, "clean", 40, "running", db)

        # Fetch stored settings (default country + scoring weights) once
        from app.routes.settings import get_current_settings
        sys_settings = get_current_settings(db) if db else {}
        default_country = sys_settings.get("country", "India")
        custom_weights = sys_settings.get("weights") if sys_settings else None

        # ----------------------------------------------------
        # STAGE 3: CLEANING & NORMALIZATION
        # ----------------------------------------------------
        t0 = time.perf_counter()
        valid_leads, rejected_rows, cleaning_logs, clean_stats = clean_and_normalize_records(
            mapped_df, run_id, default_country=default_country
        )
        timings["clean_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["clean_peak_mb"] = _get_peak_mb()
        logger.info("Pipeline %s [clean]: %.2f ms, peak: %.2f MB", run_id, timings["clean_ms"], timings["clean_peak_mb"])
        del mapped_df
        gc.collect()
        update_run_progress(run_id, "dedupe", 60, "running", db)

        # ----------------------------------------------------
        # STAGE 4: DEDUPLICATION (EXACT HASH + RAPIDFUZZ BUCKETS)
        # ----------------------------------------------------
        t0 = time.perf_counter()
        winner_leads, merged_logs, dedup_stats = fast_deduplicate_leads(
            valid_leads, run_id, threshold=85.0
        )
        timings["dedupe_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["dedupe_peak_mb"] = _get_peak_mb()
        logger.info("Pipeline %s [dedupe]: %.2f ms, peak: %.2f MB", run_id, timings["dedupe_ms"], timings["dedupe_peak_mb"])
        del valid_leads
        gc.collect()
        update_run_progress(run_id, "score", 75, "running", db)

        # ----------------------------------------------------
        # STAGE 5: SCORING ENGINE (WITH DEGRADATION FALLBACK & HUBSPOT RULES)
        # ----------------------------------------------------
        t0 = time.perf_counter()
        from app.services.hubspot_import import get_active_rules
        hs_rules = get_active_rules(db) if db else []

        scored_leads, score_summary = smart_score_leads(
            winner_leads, scoring_mode=scoring_mode, hubspot_rules=hs_rules, custom_weights=custom_weights
        )
        timings["score_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["score_peak_mb"] = _get_peak_mb()
        logger.info("Pipeline %s [score]: %.2f ms, peak: %.2f MB", run_id, timings["score_ms"], timings["score_peak_mb"])
        update_run_progress(run_id, "assign", 90, "running", db)

        # ----------------------------------------------------
        # STAGE 6: SALES REP 4-TIER ROUTING
        # ----------------------------------------------------
        t0 = time.perf_counter()
        assigned_leads, assignment_logs, assign_stats = assign_leads_in_memory(
            scored_leads, db, run_id
        )
        timings["assign_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["assign_peak_mb"] = _get_peak_mb()
        logger.info("Pipeline %s [assign]: %.2f ms, peak: %.2f MB", run_id, timings["assign_ms"], timings["assign_peak_mb"])

        # ----------------------------------------------------
        # STAGE 7: AI CLASSIFICATION (local model; Claude can be run later from the AI Classification page)
        # ----------------------------------------------------
        t0 = time.perf_counter()
        label_lead_dicts(assigned_leads)
        timings["classify_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["classify_peak_mb"] = _get_peak_mb()
        logger.info("Pipeline %s [classify]: %.2f ms, peak: %.2f MB", run_id, timings["classify_ms"], timings["classify_peak_mb"])

        # ----------------------------------------------------
        # BULK DATABASE TRANSACTIONS
        # ----------------------------------------------------
        t0 = time.perf_counter()
        # Clean any previous rows for this run_id
        # (assignment_log first: it has a foreign key to clean_leads)
        db.query(AssignmentLog).filter(AssignmentLog.run_id == run_id).delete()
        db.query(ReviewItem).filter(ReviewItem.run_id == run_id).delete()
        db.query(CleanLead).filter(CleanLead.run_id == run_id).delete()
        db.query(MergedLeadLog).filter(MergedLeadLog.run_id == run_id).delete()
        db.query(CleaningLog).filter(CleaningLog.run_id == run_id).delete()

        # Bulk save clean leads in chunks
        chunk_size = 1000
        clean_lead_models = []
        for l in assigned_leads:
            clean_lead_models.append(CleanLead(
                run_id=run_id,
                first_name=l.get("first_name"),
                last_name=l.get("last_name"),
                email=l.get("email"),
                phone=l.get("phone"),
                company=l.get("company"),
                job_title=l.get("job_title"),
                state=l.get("state"),
                city=l.get("city"),
                country=l.get("country"),
                industry=l.get("industry"),
                company_size=l.get("company_size"),
                engagement_score=l.get("engagement_score"),
                last_activity_date=l.get("last_activity_date"),
                lead_source=l.get("lead_source"),
                created_date=l.get("created_date"),
                extra_fields=l.get("extra_fields"),
                is_junk=l.get("is_junk", False),
                junk_reason=l.get("junk_reason"),
                duplicate_cluster_id=l.get("duplicate_cluster_id"),
                rule_score=l.get("rule_score"),
                ml_score=l.get("ml_score"),
                active_score=l.get("active_score"),
                score_band=l.get("score_band"),
                score_breakdown=l.get("score_breakdown"),
                assigned_rep_id=l.get("assigned_rep_id"),
                assignment_reason=l.get("assignment_reason"),
                source_row=l.get("row_index"),
                persona=l.get("persona"),
                buying_role=l.get("buying_role"),
                interest=l.get("interest"),
                classification_confidence=l.get("classification_confidence"),
                classification_engine=l.get("classification_engine"),
                recommended_action=l.get("recommended_action"),
            ))

        for i in range(0, len(clean_lead_models), chunk_size):
            db.bulk_save_objects(clean_lead_models[i:i + chunk_size])

        # Bulk save merged logs
        merged_log_models = [
            MergedLeadLog(
                run_id=run_id,
                winner_lead_id=0,  # clean_leads ids are not known before the bulk insert
                winner_raw_lead_id=m["winner_raw_lead_id"],
                archived_raw_lead_id=m["archived_raw_lead_id"],
                id_type=m["id_type"],
                archived_lead_name=m["archived_lead_name"],
                archived_company=m["archived_company"],
                archived_email=m["archived_email"],
                similarity_score=m["similarity_score"],
                merge_reason=m["merge_reason"]
            )
            for m in merged_logs
        ]
        for i in range(0, len(merged_log_models), chunk_size):
            db.bulk_save_objects(merged_log_models[i:i + chunk_size])

        # Bulk save cleaning logs
        cleaning_log_models = [
            CleaningLog(
                run_id=run_id,
                row_index=cl["row_index"],
                field_name=cl["field_name"],
                old_value=cl["old_value"],
                new_value=cl["new_value"],
                reason=cl["reason"]
            )
            for cl in cleaning_logs
        ]
        for i in range(0, len(cleaning_log_models), chunk_size):
            db.bulk_save_objects(cleaning_log_models[i:i + chunk_size])

        # Bulk save assignment logs
        assign_log_models = [
            AssignmentLog(
                run_id=run_id,
                rep_id=al["rep_id"],
                rule_matched=al["rule_matched"],
                reason=al["reason"]
            )
            for al in assignment_logs
        ]
        for i in range(0, len(assign_log_models), chunk_size):
            db.bulk_save_objects(assign_log_models[i:i + chunk_size])

        # Human review queue: borderline duplicate pairs + junk rows + phone-only / review-needed leads
        review_models = [
            ReviewItem(run_id=run_id, item_type="merge", status="pending", id_type="csv_row",
                       record_a_ref=p["a_row"], record_b_ref=p["b_row"],
                       record_a=json.dumps(_snapshot(p["a"]), default=str),
                       record_b=json.dumps(_snapshot(p["b"]), default=str),
                       similarity_score=p["similarity_score"], reason=p["reason"])
            for p in dedup_stats.get("review_pairs", [])
        ] + [
            ReviewItem(run_id=run_id, item_type="junk", status="pending", id_type="csv_row",
                       record_a_ref=l.get("row_index") or 0, record_a=json.dumps(_snapshot(l), default=str),
                       reason=l.get("junk_reason"))
            for l in assigned_leads if l.get("is_junk")
        ] + [
            ReviewItem(run_id=run_id, item_type="lead_review", status="pending", id_type="csv_row",
                       record_a_ref=l.get("row_index") or 0, record_a=json.dumps(_snapshot(l), default=str),
                       reason=l.get("review_reason") or "Lead has phone number but missing valid email address (held in Review)")
            for l in assigned_leads if l.get("needs_review") and not l.get("is_junk")
        ] + [
            # Rows dropped at cleaning (no email and no phone) are queued too; they are not in clean_leads
            ReviewItem(run_id=run_id, item_type="junk", status="pending", id_type="csv_row",
                       record_a_ref=r.get("row_number") or 0, record_a=json.dumps(r, default=str),
                       reason=f"Dropped at cleaning: {r.get('reason')}")
            for r in rejected_rows
        ]
        for i in range(0, len(review_models), chunk_size):
            db.bulk_save_objects(review_models[i:i + chunk_size])

        db.commit()
        timings["db_bulk_persist_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        timings["db_bulk_persist_peak_mb"] = _get_peak_mb()

        total_duration_ms = round((time.perf_counter() - total_start) * 1000, 2)
        timings["total_ms"] = total_duration_ms
        timings["peak_memory_mb"] = _get_peak_mb()
        try:
            tracemalloc.stop()
        except Exception:
            pass

        # Summary statistics
        summary = {
            "rows_in": rows_in,
            "rows_out": len(assigned_leads),
            "active_leads": len(assigned_leads) - clean_stats["junk_rows_count"],
            "duplicates_merged": dedup_stats["duplicates_merged"],
            "junk_removed": clean_stats["junk_rows_count"],
            "fields_fixed": clean_stats["fields_fixed_count"],
            "rejected_rows_count": len(rejected_rows),
            "borderline_pairs_queued_for_review": len(dedup_stats.get("review_pairs", [])),
            "quality_before": quality_before,
            "distribution": score_summary["distribution"],
            "total_time_ms": total_duration_ms,
            "total_time_seconds": round(total_duration_ms / 1000.0, 2)
        }

        # Update PipelineRun record
        db.query(PipelineRun).filter(PipelineRun.run_id == run_id).update({
            PipelineRun.status: "completed",
            PipelineRun.stage: "completed",
            PipelineRun.progress_percent: 100,
            PipelineRun.row_count_in: rows_in,
            PipelineRun.row_count_out: len(assigned_leads),
            PipelineRun.duplicates_merged: dedup_stats["duplicates_merged"],
            PipelineRun.junk_removed: clean_stats["junk_rows_count"],
            PipelineRun.fields_fixed: clean_stats["fields_fixed_count"],
            PipelineRun.rejected_count: len(rejected_rows),
            PipelineRun.column_mapping: json.dumps(mapping_summary),
            PipelineRun.timings: json.dumps(timings),
            PipelineRun.degraded_signals: json.dumps(score_summary["degraded_signals"]),
            PipelineRun.summary: json.dumps(summary),
            PipelineRun.rejected_rows: json.dumps(rejected_rows[:200])  # store sample/all rejected
        })
        db.commit()

        update_run_progress(run_id, "completed", 100, "completed", db)

        return sanitize_for_json({
            "success": True,
            "run_id": run_id,
            "filename": filename,
            "summary": summary,
            "column_mapping": mapping_summary,
            "degraded_signals": score_summary["degraded_signals"],
            "re_normalized_weights": score_summary["re_normalized_weights"],
            "timings": timings,
            "rejected_rows": rejected_rows
        })

    except Exception as e:
        db.rollback()
        update_run_progress(run_id, "error", 0, "failed", db)
        try:
            db.query(PipelineRun).filter(PipelineRun.run_id == run_id).update({
                PipelineRun.status: "failed",
                PipelineRun.summary: json.dumps({"error": str(e)})
            })
            db.commit()
        except Exception:
            pass
        raise e
    finally:
        if own_session:
            db.close()
