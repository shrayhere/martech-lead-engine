import os

try:
    from pydantic_settings import BaseSettings
    class Settings(BaseSettings):
        PROJECT_NAME: str = "MarTech Data Quality & Lead Scoring Engine"
        API_PREFIX: str = "/api"
        DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./martech.db")
        
        FUZZY_MATCH_THRESHOLD: float = 85.0

        WEIGHT_COMPANY_SIZE: float = 0.15
        WEIGHT_TARGET_INDUSTRY: float = 0.15
        WEIGHT_TITLE_SENIORITY: float = 0.10
        WEIGHT_ENGAGEMENT: float = 0.35
        WEIGHT_RECENCY: float = 0.25

        TARGET_INDUSTRIES: list[str] = [
            "SaaS", "Software", "Enterprise Technology", "Fintech", "Healthcare IT", "Cybersecurity", "Cloud Computing"
        ]

        C_LEVEL_KEYWORDS: list[str] = ["ceo", "cto", "cfo", "cio", "cmo", "cro", "chief", "founder", "co-founder", "president", "evp", "svp"]
        VP_DIRECTOR_KEYWORDS: list[str] = ["vice president", "vp", "head of", "director", "lead", "principal"]
        MANAGER_KEYWORDS: list[str] = ["manager", "supervising", "team lead", "senior", "sr."]

except ImportError:
    class Settings:
        PROJECT_NAME: str = "MarTech Data Quality & Lead Scoring Engine"
        API_PREFIX: str = "/api"
        DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./martech.db")
        
        FUZZY_MATCH_THRESHOLD: float = 85.0

        WEIGHT_COMPANY_SIZE: float = 0.15
        WEIGHT_TARGET_INDUSTRY: float = 0.15
        WEIGHT_TITLE_SENIORITY: float = 0.10
        WEIGHT_ENGAGEMENT: float = 0.35
        WEIGHT_RECENCY: float = 0.25

        TARGET_INDUSTRIES: list[str] = [
            "SaaS", "Software", "Enterprise Technology", "Fintech", "Healthcare IT", "Cybersecurity", "Cloud Computing"
        ]

        C_LEVEL_KEYWORDS: list[str] = ["ceo", "cto", "cfo", "cio", "cmo", "cro", "chief", "founder", "co-founder", "president", "evp", "svp"]
        VP_DIRECTOR_KEYWORDS: list[str] = ["vice president", "vp", "head of", "director", "lead", "principal"]
        MANAGER_KEYWORDS: list[str] = ["manager", "supervising", "team lead", "senior", "sr."]

settings = Settings()
