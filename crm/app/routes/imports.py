import os
import uuid

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import DuplicateRecord, ImportJob
from app.services import csv_processor, sync_engine
from app.utils.api import ApiError, audit, get_owned, json_body, paginate

bp = Blueprint("imports", __name__, url_prefix="/api/imports")


def _owned_job(import_id):
    return get_owned(ImportJob, import_id, owner_attr="user_id")


@bp.get("/fields")
@login_required
def fields():
    return jsonify(fields=[{"field": k, "label": v[0], "group": v[1]} for k, v in csv_processor.TARGET_FIELDS.items()])


@bp.post("/upload")
@login_required
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        raise ApiError("Choose a CSV file to upload.", 400)
    original = os.path.basename(file.filename)[:255]
    data = file.read(current_app.config["MAX_CONTENT_LENGTH"] + 1)
    csv_processor.validate_upload(original, data, current_app.config["MAX_CONTENT_LENGTH"])
    text, encoding, enc_warning = csv_processor.decode(data)
    delimiter = csv_processor.detect_delimiter(text)
    columns = csv_processor.read_header(text, delimiter)
    total = csv_processor.count_rows(text, delimiter)
    if total == 0:
        raise ApiError("The CSV has a header row but no data rows.", 400)
    if total > current_app.config["MAX_IMPORT_ROWS"]:
        raise ApiError(f"The file has {total:,} rows; the limit is {current_app.config['MAX_IMPORT_ROWS']:,}.", 413)
    preview, stats = csv_processor.profile(text, delimiter, columns)

    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(current_user.user_id))
    os.makedirs(folder, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.csv"
    with open(os.path.join(folder, stored), "wb") as fh:  # stored as inert data, never executed
        fh.write(data)

    job = ImportJob(user_id=current_user.user_id, original_filename=secure_filename(original) or "upload.csv",
                    stored_filename=stored, file_size=len(data), encoding=encoding, delimiter=delimiter,
                    total_rows=total, import_status="uploaded")
    db.session.add(job)
    db.session.flush()
    audit("import", job.import_id, "upload", None, {"file": job.original_filename, "rows": total})
    db.session.commit()
    warnings = [enc_warning] if enc_warning else []
    missing = [c for c in columns if c.startswith("column_")]
    if missing:
        warnings.append(f"{len(missing)} column(s) had no header name and were labelled automatically.")
    return jsonify(job=job.to_dict(), columns=columns, preview=preview, column_stats=stats,
                   suggested_mapping=csv_processor.suggest_mapping(columns), warnings=warnings,
                   delimiter_label={",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}.get(delimiter, delimiter),
                   ), 201


def _mapping_and_mode(data):
    mapping = data.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        raise ApiError("A column mapping is required.", 400)
    mapping = {str(k): (str(v) if v else "") for k, v in mapping.items()}
    mode = data.get("mode", "upsert")
    return mapping, mode


@bp.post("/preview")
@login_required
def preview():
    data = json_body()
    job = _owned_job(int(data.get("import_id") or 0))
    mapping, mode = _mapping_and_mode(data)
    return jsonify(sync_engine.run_sync(job, mapping, mode, dry_run=True))


@bp.post("/execute")
@login_required
def execute():
    data = json_body()
    job = _owned_job(int(data.get("import_id") or 0))
    mapping, mode = _mapping_and_mode(data)
    dry = mode == "dry_run" or bool(data.get("dry_run"))
    if mode == "dry_run":
        mode = data.get("base_mode", "upsert")
    result = sync_engine.run_sync(job, mapping, mode, dry_run=dry)
    return jsonify(result), (200 if dry else 201)


@bp.get("/history")
@login_required
def history():
    q = ImportJob.query.filter_by(user_id=current_user.user_id).order_by(ImportJob.upload_timestamp.desc())
    if request.args.get("status"):
        q = q.filter(ImportJob.import_status == request.args["status"])
    return jsonify(paginate(q, lambda j: j.to_dict(), default_per_page=10))


@bp.get("/<int:import_id>")
@login_required
def get_import(import_id):
    job = _owned_job(import_id)
    data = {"job": job.to_dict(), "sync_logs": [s.to_dict() for s in job.sync_logs]}
    if job.import_status in ("uploaded", "previewed"):
        try:
            text = sync_engine.load_job_text(job)
            columns = csv_processor.read_header(text, job.delimiter or ",")
            prev, stats = csv_processor.profile(text, job.delimiter or ",", columns)
            auto = csv_processor.suggest_mapping(columns)
            data.update(columns=columns, preview=prev, column_stats=stats, auto_mapping=auto,
                        suggested_mapping=job.mapping or auto)
        except ApiError as e:
            data["file_error"] = e.message
    return jsonify(data)


@bp.get("/<int:import_id>/report")
@login_required
def report(import_id):
    job = _owned_job(import_id)
    kind = request.args.get("download")
    if kind:
        path = {"success": job.success_report_path, "duplicates": job.duplicate_report_path,
                "errors": job.error_report_path}.get(kind)
        if not path or not os.path.exists(path):
            raise ApiError("This report is not available for the selected import.", 404)
        return send_file(path, mimetype="text/csv", as_attachment=True,
                         download_name=f"import_{import_id}_{kind}.csv")
    pending = DuplicateRecord.query.filter_by(import_id=import_id, resolution_status="pending").count()
    return jsonify(job=job.to_dict(), sync_logs=[s.to_dict() for s in job.sync_logs],
                   pending_duplicates=pending)


@bp.get("/<int:import_id>/errors")
@login_required
def errors(import_id):
    job = _owned_job(import_id)
    if not job.error_report_path or not os.path.exists(job.error_report_path):
        raise ApiError("This import has no failed rows.", 404)
    return send_file(job.error_report_path, mimetype="text/csv", as_attachment=True,
                     download_name=f"import_{import_id}_failed_rows.csv")
