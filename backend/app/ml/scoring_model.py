import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib
import os

MODEL_FILE_PATH = os.path.join(os.path.dirname(__file__), "lead_classifier.joblib")

class LeadMLScorer:
    """
    Scikit-Learn ML Model for predicting B2B Lead Conversion Likelihood (0-100 score).
    Uses Logistic Regression trained on synthetic historical conversion outcomes.
    """
    def __init__(self):
        self.pipeline = None
        self._load_or_train_model()

    def _generate_synthetic_training_data(self, n_samples: int = 1500) -> pd.DataFrame:
        """Generates realistic synthetic B2B training set with binary conversion labels calibrated to ~10-15% conversion."""
        np.random.seed(42)

        company_sizes = np.random.choice([10, 50, 200, 800, 2500, 10000], size=n_samples)
        is_target_industry = np.random.choice([0, 1], p=[0.4, 0.6], size=n_samples)
        seniority_levels = np.random.choice([25, 50, 80, 100], p=[0.3, 0.3, 0.25, 0.15], size=n_samples)
        engagement_scores = np.random.randint(0, 101, size=n_samples)
        days_since_activity = np.random.randint(1, 150, size=n_samples)

        # Calibrated logit formula: yields ~10% Hot conversion probability matching rule distribution
        logit = (
            -4.5
            + 0.3 * np.log1p(company_sizes / 100.0)
            + 0.6 * is_target_industry
            + 0.015 * seniority_levels
            + 0.035 * engagement_scores
            - 0.02 * days_since_activity
        )
        
        prob = 1 / (1 + np.exp(-logit))
        converted = (prob > np.random.uniform(0, 1, size=n_samples)).astype(int)

        df = pd.DataFrame({
            'company_size_log': np.log1p(company_sizes),
            'is_target_industry': is_target_industry,
            'seniority_score': seniority_levels,
            'engagement_score': engagement_scores,
            'days_since_activity': days_since_activity,
            'converted': converted
        })
        return df

    def _load_or_train_model(self):
        if os.path.exists(MODEL_FILE_PATH):
            try:
                self.pipeline = joblib.load(MODEL_FILE_PATH)
                return
            except Exception:
                pass

        # Train new model if not cached
        df = self._generate_synthetic_training_data()
        X = df[['company_size_log', 'is_target_industry', 'seniority_score', 'engagement_score', 'days_since_activity']]
        y = df['converted']

        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', LogisticRegression(max_iter=1000, random_state=42))
        ])
        pipeline.fit(X, y)
        self.pipeline = pipeline
        
        # Save model
        os.makedirs(os.path.dirname(MODEL_FILE_PATH), exist_ok=True)
        joblib.dump(pipeline, MODEL_FILE_PATH)

    def extract_features(self, lead) -> list:
        from app.config import settings
        from app.services.scoring_service import classify_seniority

        # 1. Log company size (validated > 0)
        cs = getattr(lead, "company_size", None)
        if cs is None or cs <= 0:
            cs_log = 0.0
        else:
            cs_log = float(np.log1p(cs))

        # 2. Target industry binary
        ind = getattr(lead, "industry", None) or ""
        is_target = 1 if any(t.lower() in ind.lower() for t in settings.TARGET_INDUSTRIES) else 0

        # 3. Seniority score (uses identical logic as rule-based scoring)
        title = getattr(lead, "job_title", None) or ""
        sen, _ = classify_seniority(title)

        # 4. Engagement score (validated 0-100; missing/out-of-range = 0)
        eng_raw = getattr(lead, "engagement_score", None)
        try:
            eng = float(eng_raw) if eng_raw is not None and 0 <= float(eng_raw) <= 100 else 0.0
        except (ValueError, TypeError):
            eng = 0.0

        # 5. Days since last activity (missing/future/invalid = 180 days)
        act_str = getattr(lead, "last_activity_date", None)
        try:
            act_date = datetime.strptime(str(act_str)[:10], "%Y-%m-%d")
            if act_date > datetime.now():
                days = 180
            else:
                days = (datetime.now() - act_date).days
                days = max(1, min(180, days))
        except Exception:
            days = 180

        return [cs_log, is_target, sen, eng, days]

    def predict_score(self, lead) -> float:
        """Returns predicted conversion score 0 to 100."""
        features = self.extract_features(lead)
        X = np.array([features])
        prob = self.pipeline.predict_proba(X)[0][1] # P(converted)
        return round(float(prob * 100), 1)

ml_scorer = LeadMLScorer()
