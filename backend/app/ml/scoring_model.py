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
        """Generates realistic synthetic B2B training set with binary conversion labels."""
        np.random.seed(42)

        company_sizes = np.random.choice([10, 50, 200, 800, 2500, 10000], size=n_samples)
        is_target_industry = np.random.choice([0, 1], p=[0.4, 0.6], size=n_samples)
        seniority_levels = np.random.choice([25, 50, 80, 100], p=[0.3, 0.3, 0.25, 0.15], size=n_samples)
        engagement_scores = np.random.randint(0, 101, size=n_samples)
        days_since_activity = np.random.randint(1, 150, size=n_samples)

        # Logit formula for conversion probability:
        # High engagement, recent activity, C-level, large company, target industry -> higher P(convert)
        logit = (
            -2.5 
            + 0.4 * np.log1p(company_sizes / 100.0)
            + 0.8 * is_target_industry
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

        # 1. Log company size
        cs = lead.company_size or 50
        cs_log = float(np.log1p(cs))

        # 2. Target industry binary
        ind = lead.industry or ""
        is_target = 1 if any(t.lower() in ind.lower() for t in settings.TARGET_INDUSTRIES) else 0

        # 3. Seniority score
        title = (lead.job_title or "").lower()
        if any(k in title for k in settings.C_LEVEL_KEYWORDS):
            sen = 100
        elif any(k in title for k in settings.VP_DIRECTOR_KEYWORDS):
            sen = 80
        elif any(k in title for k in settings.MANAGER_KEYWORDS):
            sen = 50
        else:
            sen = 25

        # 4. Engagement score
        eng = float(lead.engagement_score or 0)

        # 5. Days since last activity
        act_str = lead.last_activity_date or "2026-01-01"
        try:
            act_date = datetime.strptime(act_str[:10], "%Y-%m-%d")
            days = (datetime.now() - act_date).days
            days = max(1, min(180, days))
        except Exception:
            days = 60

        return [cs_log, is_target, sen, eng, days]

    def predict_score(self, lead) -> float:
        """Returns predicted conversion score 0 to 100."""
        features = self.extract_features(lead)
        X = np.array([features])
        prob = self.pipeline.predict_proba(X)[0][1] # P(converted)
        return round(float(prob * 100), 1)

ml_scorer = LeadMLScorer()
