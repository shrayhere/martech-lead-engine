import time
import json
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.schemas import RawLead, CleanLead, MergedLeadLog, CleaningLog, AssignmentLog, PipelineRun
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
    scoring_mode: str = "rule"
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

    db = SessionLocal()
    total_start = time.perf_counter()
    timings = {}

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
        timings["parse_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        update_run_progress(run_id, "map", 25, "running", db)

        # ----------------------------------------------------
        # STAGE 2: SCHEMA ABSTRACTION & MAPPING
        # ----------------------------------------------------
        t0 = time.perf_counter()
        mapped_df, mapping_summary = apply_schema_mapping(raw_df, mapping_override)
        timings["map_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        update_run_progress(run_id, "clean", 40, "running", db)

        # ----------------------------------------------------
        # STAGE 3: CLEANING & NORMALIZATION
        # ----------------------------------------------------
        t0 = time.perf_counter()
        valid_leads, rejected_rows, cleaning_logs, clean_stats = clean_and_normalize_records(
            mapped_df, run_id
        )
        timings["clean_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        update_run_progress(run_id, "dedupe", 60, "running", db)

        # ----------------------------------------------------
        # STAGE 4: DEDUPLICATION (EXACT HASH + RAPIDFUZZ BUCKETS)
        # ----------------------------------------------------
        t0 = time.perf_counter()
        winner_leads, merged_logs, dedup_stats = fast_deduplicate_leads(
            valid_leads, run_id, threshold=85.0
        )
        timings["dedupe_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        update_run_progress(run_id, "score", 75, "running", db)

        # ----------------------------------------------------
        # STAGE 5: SCORING ENGINE (WITH DEGRADATION FALLBACK)
        # ----------------------------------------------------
        t0 = time.perf_counter()
        scored_leads, score_summary = smart_score_leads(
            winner_leads, scoring_mode=scoring_mode
        )
        timings["score_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        update_run_progress(run_id, "assign", 90, "running", db)

        # ----------------------------------------------------
        # STAGE 6: SALES REP 4-TIER ROUTING
        # ----------------------------------------------------
        t0 = time.perf_counter()
        assigned_leads, assignment_logs, assign_stats = assign_leads_in_memory(
            scored_leads, db, run_id
        )
        timings["assign_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # ----------------------------------------------------
        # BULK DATABASE TRANSACTIONS
        # ----------------------------------------------------
        t0 = time.perf_counter()
        # Clean any previous rows for this run_id
        db.query(CleanLead).filter(CleanLead.run_id == run_id).delete()
        db.query(MergedLeadLog).filter(MergedLeadLog.run_id == run_id).delete()
        db.query(CleaningLog).filter(CleaningLog.run_id == run_id).delete()
        db.query(AssignmentLog).filter(AssignmentLog.run_id == run_id).delete()

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
                assignment_reason=l.get("assignment_reason")
            ))

        for i in range(0, len(clean_lead_models), chunk_size):
            db.bulk_save_objects(clean_lead_models[i:i + chunk_size])

        # Bulk save merged logs
        merged_log_models = [
            MergedLeadLog(
                run_id=run_id,
                winner_lead_id=0,  # cluster leader
                archived_raw_lead_id=m["archived_raw_lead_id"],
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

        db.commit()
        timings["db_bulk_persist_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        total_duration_ms = round((time.perf_counter() - total_start) * 1000, 2)
        timings["total_ms"] = total_duration_ms

        # Summary statistics
        summary = {
            "rows_in": len(raw_df),
            "rows_out": len(assigned_leads),
            "duplicates_merged": dedup_stats["duplicates_merged"],
            "junk_removed": clean_stats["junk_rows_count"],
            "fields_fixed": clean_stats["fields_fixed_count"],
            "rejected_rows_count": len(rejected_rows),
            "distribution": score_summary["distribution"],
            "total_time_ms": total_duration_ms,
            "total_time_seconds": round(total_duration_ms / 1000.0, 2)
        }

        # Update PipelineRun record
        db.query(PipelineRun).filter(PipelineRun.run_id == run_id).update({
            PipelineRun.status: "completed",
            PipelineRun.stage: "completed",
            PipelineRun.progress_percent: 100,
            PipelineRun.row_count_in: len(raw_df),
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

        return {
            "success": True,
            "run_id": run_id,
            "filename": filename,
            "summary": summary,
            "column_mapping": mapping_summary,
            "degraded_signals": score_summary["degraded_signals"],
            "re_normalized_weights": score_summary["re_normalized_weights"],
            "timings": timings,
            "rejected_rows": rejected_rows
        }

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
        db.close()
