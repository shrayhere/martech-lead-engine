import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import SystemSetting

router = APIRouter(prefix="/settings", tags=["System Settings"])

DEFAULT_WEIGHTS = {
    "company_size": 15,
    "target_industry": 15,
    "title_seniority": 10,
    "engagement": 35,
    "recency": 25,
}
DEFAULT_COUNTRY = "India"


class SettingsPayload(BaseModel):
    country: str = Field(default=DEFAULT_COUNTRY)
    weights: Dict[str, float]


def get_current_settings(db: Session) -> Dict[str, Any]:
    """Helper to fetch settings from DB or defaults."""
    try:
        country_row = db.query(SystemSetting).filter(SystemSetting.key == "default_country").first()
        country = country_row.value if country_row else DEFAULT_COUNTRY
    except Exception:
        country = DEFAULT_COUNTRY

    try:
        weights_row = db.query(SystemSetting).filter(SystemSetting.key == "scoring_weights").first()
        if weights_row:
            try:
                weights = json.loads(weights_row.value)
            except Exception:
                weights = DEFAULT_WEIGHTS.copy()
        else:
            weights = DEFAULT_WEIGHTS.copy()
    except Exception:
        weights = DEFAULT_WEIGHTS.copy()

    return {"country": country, "weights": weights}


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    """Fetch stored scoring weights and default localization country."""
    return get_current_settings(db)


@router.put("")
def update_settings(payload: SettingsPayload, db: Session = Depends(get_db)):
    """Update system settings with validation."""
    # Validate weights sum to 100
    total = sum(payload.weights.values())
    if abs(total - 100.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Scoring weights must sum to 100%. Current sum: {total:.1f}%")

    required_keys = {"company_size", "target_industry", "title_seniority", "engagement", "recency"}
    if not required_keys.issubset(payload.weights.keys()):
        missing = required_keys - set(payload.weights.keys())
        raise HTTPException(status_code=400, detail=f"Missing weight keys: {', '.join(missing)}")

    for k, v in payload.weights.items():
        if v < 0:
            raise HTTPException(status_code=400, detail=f"Weight for '{k}' cannot be negative.")

    try:
        # Upsert country
        c_row = db.query(SystemSetting).filter(SystemSetting.key == "default_country").first()
        if not c_row:
            c_row = SystemSetting(key="default_country", value=payload.country.strip())
            db.add(c_row)
        else:
            c_row.value = payload.country.strip()

        # Upsert weights
        w_row = db.query(SystemSetting).filter(SystemSetting.key == "scoring_weights").first()
        w_json = json.dumps({k: float(v) for k, v in payload.weights.items()})
        if not w_row:
            w_row = SystemSetting(key="scoring_weights", value=w_json)
            db.add(w_row)
        else:
            w_row.value = w_json

        db.commit()
        return {"success": True, "settings": {"country": c_row.value, "weights": payload.weights}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")
