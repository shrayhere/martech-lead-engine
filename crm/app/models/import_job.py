import json

from app.extensions import db
from app.models.base import iso, utcnow

IMPORT_STATUSES = ("uploaded", "previewed", "processing", "completed", "failed", "rolled_back")
SYNC_MODES = ("insert_only", "update_existing", "upsert")


class DataSource(db.Model):
    __tablename__ = "data_sources"

    source_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_name = db.Column(db.String(120), nullable=False)
    source_type = db.Column(db.String(30), nullable=False)  # manual | csv | seed | api
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("owner_id", "source_name", name="uq_data_source_owner_name"),
    )

    def to_dict(self):
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "description": self.description,
            "created_at": iso(self.created_at),
        }


class ImportJob(db.Model):
    __tablename__ = "csv_import_jobs"

    import_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    upload_timestamp = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    encoding = db.Column(db.String(30))
    delimiter = db.Column(db.String(5))
    total_rows = db.Column(db.Integer, nullable=False, default=0)
    successful_rows = db.Column(db.Integer, nullable=False, default=0)
    inserted_rows = db.Column(db.Integer, nullable=False, default=0)
    updated_rows = db.Column(db.Integer, nullable=False, default=0)
    failed_rows = db.Column(db.Integer, nullable=False, default=0)
    duplicate_rows = db.Column(db.Integer, nullable=False, default=0)
    skipped_rows = db.Column(db.Integer, nullable=False, default=0)
    import_status = db.Column(db.String(20), nullable=False, default="uploaded", index=True)
    sync_mode = db.Column(db.String(20))
    column_mapping = db.Column(db.Text)  # JSON {csv_column: target_field}
    error_report_path = db.Column(db.String(255))
    duplicate_report_path = db.Column(db.String(255))
    success_report_path = db.Column(db.String(255))
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)

    sync_logs = db.relationship("SyncLog", back_populates="import_job", cascade="all, delete-orphan",
                                passive_deletes=True)

    __table_args__ = (
        db.CheckConstraint(
            "import_status IN ('uploaded','previewed','processing','completed','failed','rolled_back')",
            name="import_status_valid"),
    )

    @property
    def mapping(self):
        return json.loads(self.column_mapping) if self.column_mapping else {}

    def to_dict(self):
        return {
            "import_id": self.import_id,
            "original_filename": self.original_filename,
            "upload_timestamp": iso(self.upload_timestamp),
            "file_size": self.file_size,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "total_rows": self.total_rows,
            "successful_rows": self.successful_rows,
            "inserted_rows": self.inserted_rows,
            "updated_rows": self.updated_rows,
            "failed_rows": self.failed_rows,
            "duplicate_rows": self.duplicate_rows,
            "skipped_rows": self.skipped_rows,
            "import_status": self.import_status,
            "sync_mode": self.sync_mode,
            "column_mapping": self.mapping,
            "has_error_report": bool(self.error_report_path),
            "has_duplicate_report": bool(self.duplicate_report_path),
            "has_success_report": bool(self.success_report_path),
            "error_message": self.error_message,
            "started_at": iso(self.started_at),
            "completed_at": iso(self.completed_at),
            "duration_ms": self.duration_ms,
        }


class SyncLog(db.Model):
    __tablename__ = "sync_logs"

    sync_id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(
        db.Integer, db.ForeignKey("csv_import_jobs.import_id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id = db.Column(
        db.Integer, db.ForeignKey("data_sources.source_id", ondelete="SET NULL"), nullable=True, index=True
    )
    sync_type = db.Column(db.String(20), nullable=False)
    records_inserted = db.Column(db.Integer, nullable=False, default=0)
    records_updated = db.Column(db.Integer, nullable=False, default=0)
    records_skipped = db.Column(db.Integer, nullable=False, default=0)
    records_failed = db.Column(db.Integer, nullable=False, default=0)
    sync_status = db.Column(db.String(20), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)

    import_job = db.relationship("ImportJob", back_populates="sync_logs")
    source = db.relationship("DataSource")

    def to_dict(self):
        return {
            "sync_id": self.sync_id,
            "import_id": self.import_id,
            "source": self.source.to_dict() if self.source else None,
            "sync_type": self.sync_type,
            "records_inserted": self.records_inserted,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "records_failed": self.records_failed,
            "sync_status": self.sync_status,
            "started_at": iso(self.started_at),
            "completed_at": iso(self.completed_at),
        }
