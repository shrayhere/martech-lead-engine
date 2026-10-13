import json
import uuid
import io
import csv
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import PipelineRun
from app.services.pipeline_service import execute_smart_pipeline, FILE_CACHE, RUN_PROGRESS

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

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

    if async_mode:
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
            "message": "Pipeline initiated in background task."
        }
    else:
        try:
            result = execute_smart_pipeline(
                file_bytes=file_bytes,
                filename=filename,
                run_id=current_run_id,
                mapping_override=parsed_override,
                scoring_mode=scoring_mode
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
            writer.writerow(row)
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
