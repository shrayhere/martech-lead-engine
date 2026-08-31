import os
from pydantic_settings import BaseSettings if os.path.exists("pydantic_settings") else object

class Settings:
    PROJECT_NAME: str = "MarTech Data Quality & Lead Scoring Engine"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./martech.db")
    
    # RapidFuzz deduplication similarity threshold
    # Chosen at 85% based on empirical testing on B2B lead datasets:
    # 85% catches typos like "Johnathan Smith" vs "Jonathan Smith", "Acme Corp" vs "Acme Inc"
    # while avoiding false positives between distinct names/companies.
    FUZZY_MATCH_THRESHOLD: float = 85.0

    # Rule-Based Lead Scoring Configurable Weights (Sum to 1.0)
    # Firmographic Weights (40% total)
    WEIGHT_COMPANY_SIZE: float = 0.15
    WEIGHT_TARGET_INDUSTRY: float = 0.15
    WEIGHT_TITLE_SENIORITY: float = 0.10

    # Behavioral Weights (60% total)
    WEIGHT_ENGAGEMENT: float = 0.35
    WEIGHT_RECENCY: float = 0.25

    # Target High-Value Industries
    TARGET_INDUSTRIES: list[str] = [
        "SaaS", "Software", "Enterprise Technology", "Fintech", "Healthcare IT", "Cybersecurity", "Cloud Computing"
    ]

    # Seniority Keywords mapping
    C_LEVEL_KEYWORDS: list[str] = ["ceo", "cto", "cfo", "cio", "cmo", "cro", "chief", "founder", "co-founder", "president", "evp", "svp"]
    VP_DIRECTOR_KEYWORDS: list[str] = ["vice president", "vp", "head of", "director", "lead", "principal"]
    MANAGER_KEYWORDS: list[str] = ["manager", "supervising", "team lead", "senior", "sr."]

settings = Settings()
