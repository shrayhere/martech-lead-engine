"""Dashboard / report aggregations — all computed in SQL from live records."""
from datetime import date, datetime, timedelta

from sqlalchemy import and_, case, func, true

from app.extensions import db
from app.models import LEAD_STAGES, LIFECYCLE_STAGES, Company, Contact, ImportJob
from app.models.base import utcnow
from app.utils.api import ApiError

RANGES = {"today": 0, "7d": 7, "30d": 30, "90d": 90}
effective_category = func.coalesce(Contact.lead_category_override, Contact.lead_category)


def resolve_range(range_key, start=None, end=None):
    """Return (start, end) naive-UTC datetimes or (None, None) for all time."""
    now = utcnow()
    if not range_key or range_key == "all":
        return None, None
    if range_key == "today":
        s = datetime(now.year, now.month, now.day)
        return s, now
    if range_key in RANGES:
        return now - timedelta(days=RANGES[range_key]), now
    if range_key == "custom":
        if not start or not end:
            raise ApiError("A custom range needs both a start and an end date.", 400)
        if start > end:
            raise ApiError("The start date must be before the end date.", 400)
        return start, end
    raise ApiError("Unknown date range.", 400)


def _in_range(column, start, end):
    conds = []
    if start:
        conds.append(column >= start)
    if end:
        conds.append(column <= end)
    return and_(*conds) if conds else true()


def stats(owner_id, start=None, end=None):
    in_range = _in_range(Contact.created_at, start, end)
    base = db.session.query(
        func.count(Contact.contact_id),
        func.sum(case((and_(Contact.lifecycle_stage.in_(LEAD_STAGES), effective_category.isnot(None)), 1), else_=0)),
        func.sum(case((and_(Contact.lifecycle_stage.in_(LEAD_STAGES), effective_category == "hot"), 1), else_=0)),
        func.sum(case((and_(Contact.lifecycle_stage.in_(LEAD_STAGES), effective_category == "warm"), 1), else_=0)),
        func.sum(case((and_(Contact.lifecycle_stage.in_(LEAD_STAGES), effective_category == "cold"), 1), else_=0)),
        func.avg(Contact.lead_score),
    ).filter(Contact.owner_id == owner_id, in_range).one()
    total, leads, hot, warm, cold, avg = base
    companies = db.session.query(func.count(Company.company_id)).filter(
        Company.owner_id == owner_id, _in_range(Company.created_at, start, end)).scalar()
    now = utcnow()
    month_start = datetime(now.year, now.month, 1)
    new_this_month = db.session.query(func.count(Contact.contact_id)).filter(
        Contact.owner_id == owner_id, Contact.created_at >= month_start).scalar()
    imports_done = db.session.query(func.count(ImportJob.import_id)).filter(
        ImportJob.user_id == owner_id, ImportJob.import_status == "completed",
        _in_range(ImportJob.upload_timestamp, start, end)).scalar()
    return {
        "total_contacts": total or 0,
        "total_companies": companies or 0,
        "total_leads": int(leads or 0),
        "hot_leads": int(hot or 0),
        "warm_leads": int(warm or 0),
        "cold_leads": int(cold or 0),
        "new_contacts_this_month": new_this_month or 0,
        "imports_completed": imports_done or 0,
        "average_lead_score": round(float(avg), 1) if avg is not None else 0,
    }


def _days(start, end, owner_id):
    if start is None:
        first = db.session.query(func.min(Contact.created_at)).filter(Contact.owner_id == owner_id).scalar()
        start = first or utcnow() - timedelta(days=30)
    end = end or utcnow()
    return start, end


def _to_date(value):
    if isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _bucketed(rows, start, end, width):
    """rows: [(date, *values)] -> labels + series bucketed by day (<=62 days) or ISO week."""
    span = (end.date() - start.date()).days + 1
    weekly = span > 62
    buckets = {}
    cursor = start.date()
    while cursor <= end.date():
        key = cursor - timedelta(days=cursor.weekday()) if weekly else cursor
        buckets.setdefault(key, None)
        cursor += timedelta(days=1)
    labels = list(buckets.keys())

    series = {k: [0] * width for k in labels}
    for row in rows:
        d = _to_date(row[0])
        key = d - timedelta(days=d.weekday()) if weekly else d
        if key in series:
            series[key] = [a + int(b or 0) for a, b in zip(series[key], row[1:])]
    return [k.isoformat() for k in labels], [series[k] for k in labels], ("week" if weekly else "day")


def charts(owner_id, start=None, end=None):
    in_range = _in_range(Contact.created_at, start, end)
    owner = Contact.owner_id == owner_id

    dist = dict(db.session.query(effective_category, func.count(Contact.contact_id)).filter(
        owner, in_range, Contact.lifecycle_stage.in_(LEAD_STAGES), effective_category.isnot(None)
    ).group_by(effective_category).all())

    s, e = _days(start, end, owner_id)
    day = func.date(Contact.created_at)
    rows = db.session.query(
        day,
        func.count(Contact.contact_id),
        func.sum(case((effective_category == "hot", 1), else_=0)),
        func.sum(case((effective_category == "warm", 1), else_=0)),
        func.sum(case((effective_category == "cold", 1), else_=0)),
    ).filter(owner, Contact.created_at >= s, Contact.created_at <= e,
             Contact.lifecycle_stage.in_(LEAD_STAGES)).group_by(day).order_by(day).all()
    labels, values, granularity = _bucketed(rows, s, e, 4)

    by_company = db.session.query(Company.company_name, func.count(Contact.contact_id)).join(
        Contact, Contact.company_id == Company.company_id).filter(
        Company.owner_id == owner_id, in_range).group_by(Company.company_id, Company.company_name).order_by(
        func.count(Contact.contact_id).desc()).limit(10).all()
    no_company = db.session.query(func.count(Contact.contact_id)).filter(
        owner, in_range, Contact.company_id.is_(None)).scalar()

    sources = db.session.query(func.coalesce(Contact.lead_source, "Unknown"), func.count(Contact.contact_id)).filter(
        owner, in_range).group_by(func.coalesce(Contact.lead_source, "Unknown")).order_by(
        func.count(Contact.contact_id).desc()).all()

    imp_day = func.date(ImportJob.upload_timestamp)
    imp_rows = db.session.query(
        imp_day, func.count(ImportJob.import_id),
        func.coalesce(func.sum(ImportJob.inserted_rows), 0), func.coalesce(func.sum(ImportJob.updated_rows), 0),
        func.coalesce(func.sum(ImportJob.failed_rows), 0),
    ).filter(ImportJob.user_id == owner_id, ImportJob.import_status == "completed",
             ImportJob.upload_timestamp >= s, ImportJob.upload_timestamp <= e).group_by(imp_day).order_by(imp_day).all()
    imp_labels, imp_values, imp_gran = _bucketed(imp_rows, s, e, 4)

    stage_counts = dict(db.session.query(Contact.lifecycle_stage, func.count(Contact.contact_id)).filter(
        owner, in_range).group_by(Contact.lifecycle_stage).all())
    funnel_order = ["subscriber", "lead", "mql", "sql", "opportunity", "customer"]
    funnel = []
    for i, stage in enumerate(funnel_order):
        reached = sum(stage_counts.get(s2, 0) for s2 in funnel_order[i:]) + (
            stage_counts.get("evangelist", 0))
        funnel.append({"stage": stage, "count": stage_counts.get(stage, 0), "reached": reached})

    return {
        "range": {"start": s.isoformat(), "end": e.isoformat(), "granularity": granularity},
        "lead_distribution": {"hot": dist.get("hot", 0), "warm": dist.get("warm", 0), "cold": dist.get("cold", 0)},
        "leads_over_time": {
            "labels": labels,
            "total": [v[0] for v in values], "hot": [v[1] for v in values],
            "warm": [v[2] for v in values], "cold": [v[3] for v in values],
        },
        "contacts_by_company": {"labels": [r[0] for r in by_company], "values": [r[1] for r in by_company],
                                "without_company": no_company or 0},
        "lead_sources": {"labels": [r[0] for r in sources], "values": [r[1] for r in sources]},
        "import_history": {
            "labels": imp_labels, "granularity": imp_gran,
            "imports": [v[0] for v in imp_values], "inserted": [v[1] for v in imp_values],
            "updated": [v[2] for v in imp_values], "failed": [v[3] for v in imp_values],
        },
        "funnel": funnel,
        "lifecycle_stages": {st: stage_counts.get(st, 0) for st in LIFECYCLE_STAGES},
    }


def lead_analytics(owner_id):
    owner = Contact.owner_id == owner_id
    leads = and_(owner, Contact.lifecycle_stage.in_(LEAD_STAGES))
    by_source = db.session.query(
        func.coalesce(Contact.lead_source, "Unknown"), func.count(Contact.contact_id), func.avg(Contact.lead_score),
        func.sum(case((effective_category == "hot", 1), else_=0)),
    ).filter(leads).group_by(func.coalesce(Contact.lead_source, "Unknown")).all()
    buckets = db.session.query(
        func.sum(case((Contact.lead_score < 30, 1), else_=0)),
        func.sum(case((and_(Contact.lead_score >= 30, Contact.lead_score < 60), 1), else_=0)),
        func.sum(case((Contact.lead_score >= 60, 1), else_=0)),
        func.count(Contact.contact_id),
        func.sum(case((Contact.lead_category_override.isnot(None), 1), else_=0)),
        func.sum(case((Contact.lead_category.is_(None), 1), else_=0)),
    ).filter(leads).one()
    return {
        "by_source": [{"source": s, "leads": n, "average_score": round(float(a or 0), 1), "hot": int(h or 0)}
                      for s, n, a, h in by_source],
        "score_bands": {"0-29": int(buckets[0] or 0), "30-59": int(buckets[1] or 0), "60-100": int(buckets[2] or 0)},
        "total_leads": buckets[3] or 0,
        "manual_overrides": int(buckets[4] or 0),
        "excluded": int(buckets[5] or 0),
    }
