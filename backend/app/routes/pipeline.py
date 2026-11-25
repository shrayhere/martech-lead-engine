import json
import uuid
import io
import csv
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import PipelineRun, CleanLead
from app.services.pipeline_service import execute_smart_pipeline, FILE_CACHE, RUN_PROGRESS
from app.utils.security import sanitize_csv_cell

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

@router.post("/demo")
async def run_demo_pipeline(
    db: Session = Depends(get_db)
):
    """
    Loads messy 1,000-lead sample dataset and executes the complete pipeline end-to-end.
    """
    import os
    sample_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "tests", "fixtures", "1000_rows.csv"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "crm", "samples", "01_first_import.csv")
    ]
    file_bytes = None
    filename = "sample_1000_leads.csv"
    for p in sample_paths:
        if os.path.exists(p):
            with open(p, "rb") as f:
                file_bytes = f.read()
            filename = os.path.basename(p)
            break

    if not file_bytes:
        # Generate inline synthetic 500 leads if fixture not found
        import io
        buf = io.StringIO()
        buf.write("first_name,last_name,email,company,job_title,phone,state,industry,engagement_score,last_activity_date\n")
        titles = ["VP Engineering", "Head of Growth", "Director Sales", "CTO", "Intern", "Founder & CEO", "Operations Manager"]
        industries = ["Software", "Fintech", "Healthcare IT", "E-commerce", "SaaS"]
        states = ["Maharashtra", "Karnataka", "California", "Tamil Nadu", "New York"]
        for i in range(1, 501):
            t = titles[i % len(titles)]
            ind = industries[i % len(industries)]
            st = states[i % len(states)]
            buf.write(f"Lead{i},Sample{i},lead{i}@examplecorp.in,Acme {i % 20} Inc,{t},98765{i:05d},{st},{ind},{(i * 17) % 100},2026-10-15\n")
        file_bytes = buf.getvalue().encode("utf-8")
        filename = "synthetic_sample_500.csv"

    demo_run_id = f"demo-{uuid.uuid4().hex[:8]}"
    result = execute_smart_pipeline(
        file_bytes=file_bytes,
        filename=filename,
        run_id=demo_run_id,
        scoring_mode="rule",
        db=db
    )
    return result

@router.post("/check-duplicates")
async def check_cross_upload_duplicates(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Checks how many leads in the incoming file already exist in previous runs
    in the database (matching by exact email or phone number).
    Returns count and prompt: 'X leads already exist; update or skip?'
    """
    file_bytes = await file.read()
    filename = file.filename
    try:
        from app.services.smart_parser import parse_csv_file
        from app.services.schema_mapper import apply_schema_mapping
        raw_df, _ = parse_csv_file(file_bytes, filename)
        mapped_df, _ = apply_schema_mapping(raw_df)

        incoming_emails = set(mapped_df["email"].dropna().astype(str).str.strip().str.lower())
        incoming_phones = set(mapped_df["phone"].dropna().astype(str).str.strip())

        existing_emails = set(
            r[0].lower() for r in db.query(CleanLead.email)
            .filter(CleanLead.email.in_(incoming_emails), CleanLead.is_junk == False).all() if r[0]
        )
        existing_phones = set(
            r[0] for r in db.query(CleanLead.phone)
            .filter(CleanLead.phone.in_(incoming_phones), CleanLead.is_junk == False).all() if r[0]
        )

        match_count = len(existing_emails.union(existing_phones))
        return {
            "duplicate_count": match_count,
            "total_rows": len(mapped_df),
            "message": f"{match_count} leads already exist; update or skip?" if match_count > 0 else "No existing duplicates found."
        }
    except Exception as e:
        return {"duplicate_count": 0, "message": str(e)}

@router.post("/run")
async def run_pipeline(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    run_id: Optional[str] = Form(None),
    mapping_override: Optional[str] = Form(None),
    scoring_mode: Optional[str] = Form("rule"),
    async_mode: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    """
    Executes the one-shot smart upload pipeline:
    - Parses CSV (with encoding/delimiter autodetection).
    - Infers schema mapping using 3-tier matching.
    - Cleans & normalizes records and logs changes.
    - Deduplicates using exact hash lookups + RapidFuzz 85% blocking buckets.
    - Scores leads with graceful degradation.
    - Assigns reps via 4-tier routing rules.
    - If async_mode is true, runs in background and returns initial run_id.
    - If file is omitted, uses cached file bytes from a previous run_id with new mapping_override.
    """
    parsed_override = None
    if mapping_override:
        try:
            parsed_override = json.loads(mapping_override)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON in mapping_override.")

    # Determine file bytes
    file_bytes = None
    filename = "upload.csv"

    if file is not None:
        filename = file.filename
        file_bytes = await file.read()
    elif run_id and run_id in FILE_CACHE:
        file_bytes = FILE_CACHE[run_id]
        # Look up existing run's filename
        prev_run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if prev_run:
            filename = prev_run.filename
    else:
        raise HTTPException(
            status_code=400,
            detail="Either a CSV file must be uploaded or a valid existing run_id provided for re-running."
        )

    current_run_id = run_id or str(uuid.uuid4())

    is_large_file = file_bytes is not None and file_bytes.count(b"\n") > 5000
    should_run_bg = async_mode or is_large_file

    if should_run_bg:
        background_tasks.add_task(
            execute_smart_pipeline,
            file_bytes=file_bytes,
            filename=filename,
            run_id=current_run_id,
            mapping_override=parsed_override,
            scoring_mode=scoring_mode
        )
        return {
            "success": True,
            "run_id": current_run_id,
            "filename": filename,
            "status": "running",
            "message": f"Pipeline running in background for large file (>5,000 rows). Poll /api/pipeline/status/{current_run_id}" if is_large_file else "Pipeline initiated in background task."
        }
    else:
        try:
            result = execute_smart_pipeline(
                file_bytes=file_bytes,
                filename=filename,
                run_id=current_run_id,
                mapping_override=parsed_override,
                scoring_mode=scoring_mode,
                db=db
            )
            return result
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Pipeline processing failed: {str(e)}")

@router.get("/status/{run_id}")
def get_pipeline_status(run_id: str, db: Session = Depends(get_db)):
    """
    Returns live progress and details for a pipeline run.
    """
    # Check in-memory live progress first
    mem_progress = RUN_PROGRESS.get(run_id)

    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run and not mem_progress:
        raise HTTPException(status_code=404, detail="Pipeline run not found.")

    status = run.status if run else mem_progress.get("status")
    stage = run.stage if run else mem_progress.get("stage")
    percent = run.progress_percent if run else mem_progress.get("progress_percent")

    summary_dict = json.loads(run.summary) if (run and run.summary) else None
    timings_dict = json.loads(run.timings) if (run and run.timings) else None
    mapping_dict = json.loads(run.column_mapping) if (run and run.column_mapping) else None

    return {
        "run_id": run_id,
        "status": status,
        "stage": stage,
        "progress_percent": percent,
        "summary": summary_dict,
        "timings": timings_dict,
        "column_mapping": mapping_dict,
        "created_at": run.created_at if run else None
    }

@router.get("/runs")
def list_pipeline_runs(limit: int = 50, db: Session = Depends(get_db)):
    """
    Returns historical list of pipeline runs for the UI run selector.
    """
    runs = db.query(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(limit).all()
    results = []
    for r in runs:
        summary_obj = json.loads(r.summary) if r.summary else {}
        results.append({
            "run_id": r.run_id,
            "filename": r.filename,
            "status": r.status,
            "row_count_in": r.row_count_in,
            "row_count_out": r.row_count_out,
            "duplicates_merged": r.duplicates_merged,
            "junk_removed": r.junk_removed,
            "fields_fixed": r.fields_fixed,
            "total_time_ms": summary_obj.get("total_time_ms"),
            "created_at": r.created_at
        })
    return {
        "count": len(results),
        "runs": results
    }

@router.get("/rejected/{run_id}")
def get_rejected_rows(run_id: str, format: str = "json", db: Session = Depends(get_db)):
    """
    Retrieves or downloads the list of rows rejected during pipeline cleaning.
    """
    run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found.")

    rejected_list = json.loads(run.rejected_rows or "[]")

    if format.lower() == "csv":
        output = io.StringIO()
        fieldnames = ["row_number", "first_name", "last_name", "company", "reason"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rejected_list:
            sanitized_row = {k: sanitize_csv_cell(v) for k, v in row.items()}
            writer.writerow(sanitized_row)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=rejected_rows_{run_id[:8]}.csv"}
        )

    return {
        "run_id": run_id,
        "count": len(rejected_list),
        "rejected_rows": rejected_list
    }
