import pandas as pd
import random
from datetime import datetime, timedelta

def generate_sample_leads_csv(num_records: int = 200) -> str:
    """
    Generates a realistic synthetic B2B leads dataset of 200 rows with intentional data quality issues:
    - ~15% duplicate/near-duplicate entries with minor typos in names or company names.
    - ~5% obvious junk rows (missing phone AND email, placeholder company like 'test', 'n/a', 'asdf').
    - Inconsistent state naming ('California', 'CA', 'calif', 'Texas', 'TX', 'New York', 'ny').
    - Inconsistent phone formatting ('(555) 234-5678', '+15552345678', '555.234.5678').
    - Varied company sizes, engagement scores (0-100), and activity recency dates.
    """
    random.seed(42)

    first_names = [
        "Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Pat", "Riley", "Casey", "Dakota",
        "Avery", "Reese", "Quinn", "Skyler", "Cameron", "Peyton", "Rowan", "Hayden", "Emerson", "Finley",
        "Jonathan", "Elizabeth", "Alexander", "Katherine", "Benjamin", "Victoria", "Christopher", "Samantha"
    ]
    
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
    ]

    companies = [
        "Acme Corp", "TechFlow Inc", "CloudScale Dynamics", "Nexus AI Solutions", "Apex Global",
        "CyberShield Enterprise", "DataPulse Systems", "OmniChannel Media", "HyperGrowth Marketing",
        "Vanguard Analytics", "Peak Performance SaaS", "Synergy Tech", "Horizon Financial", "Elevate Health"
    ]

    titles = [
        "Chief Executive Officer", "CEO & Co-Founder", "VP of Sales", "Director of Marketing",
        "Senior Demand Generation Manager", "Growth Lead", "Head of Business Development",
        "Chief Technology Officer", "VP of Product", "Marketing Specialist", "Sales Operations Manager",
        "Account Executive", "Business Development Rep", "Software Engineer", "Operations Lead"
    ]

    industries = [
        "SaaS", "Software", "Enterprise Technology", "Fintech", "Healthcare IT", "Cybersecurity",
        "Cloud Computing", "Retail", "Manufacturing", "Education", "Consulting", "Real Estate"
    ]

    state_variants = {
        "CA": ["CA", "California", "calif", "Calif.", "ca"],
        "NY": ["NY", "New York", "N.Y.", "new york", "ny"],
        "TX": ["TX", "Texas", "tex", "tx"],
        "FL": ["FL", "Florida", "florida", "fl"],
        "WA": ["WA", "Washington", "wash", "wa"],
        "IL": ["IL", "Illinois", "illinois", "il"],
        "MA": ["MA", "Massachusetts", "mass", "ma"]
    }

    base_records = []
    
    # 1. Generate core 170 clean/semi-messy records
    for i in range(170):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        comp = random.choice(companies)
        
        # Occasional mixed casing for company
        if random.random() < 0.2:
            comp_casing = comp.lower() if random.random() < 0.5 else comp.upper()
        else:
            comp_casing = comp
            
        domain = comp.lower().replace(" ", "").replace("&", "").replace(".", "") + ".com"
        email = f"{fn.lower()}.{ln.lower()}@{domain}"
        
        state_key = random.choice(list(state_variants.keys()))
        state_val = random.choice(state_variants[state_key])
        
        # Phone formatting variations
        area = random.randint(200, 999)
        prefix = random.randint(200, 999)
        line = random.randint(1000, 9999)
        phone_fmt = random.choice([
            f"({area}) {prefix}-{line}",
            f"+1{area}{prefix}{line}",
            f"{area}-{prefix}-{line}",
            f"{area}.{prefix}.{line}",
            f"{area}{prefix}{line}"
        ])
        
        # Activity date within past 120 days
        days_ago = random.randint(1, 120)
        act_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        
        base_records.append({
            "first_name": fn,
            "last_name": ln,
            "email": email,
            "company": comp_casing,
            "job_title": random.choice(titles),
            "phone": phone_fmt,
            "state": state_val,
            "industry": random.choice(industries),
            "company_size": random.choice([15, 50, 120, 350, 750, 1500, 5000, 12000]),
            "engagement_score": random.randint(10, 98),
            "last_activity_date": act_date
        })

    # 2. Add 20 duplicate / near-duplicate records (Fuzzy Match targets)
    duplicates = []
    for i in range(20):
        target = base_records[i * 8]
        dup = target.copy()
        
        dup_type = i % 4
        if dup_type == 0:
            # Minor name typo: e.g., "Jonathan" -> "Jonathon"
            dup["first_name"] = dup["first_name"] + "n" if not dup["first_name"].endswith("n") else dup["first_name"][:-1] + "m"
        elif dup_type == 1:
            # Company typo / variant: e.g. "Acme Corp" -> "Acme Corporation"
            dup["company"] = dup["company"] + " Inc" if "Inc" not in dup["company"] else dup["company"].replace("Inc", "Corporation")
        elif dup_type == 2:
            # Slightly modified email or uppercase state
            dup["email"] = dup["email"].replace("@", ".lead@")
        else:
            # Lowercase name and slightly different phone
            dup["first_name"] = dup["first_name"].lower()
            dup["last_name"] = dup["last_name"].lower()

        dup["engagement_score"] = random.randint(5, 95)
        duplicates.append(dup)

    # 3. Add 10 obvious Junk records
    junk_rows = [
        {"first_name": "Test", "last_name": "User", "email": None, "company": "test company", "job_title": "Tester", "phone": None, "state": "CA", "industry": "SaaS", "company_size": 10, "engagement_score": 0, "last_activity_date": "2026-01-01"},
        {"first_name": "asdf", "last_name": "asdf", "email": "asdf@asdf.com", "company": "n/a", "job_title": "none", "phone": "0000000000", "state": "unknown", "industry": "Other", "company_size": 1, "engagement_score": 2, "last_activity_date": "2025-11-10"},
        {"first_name": "John", "last_name": "Doe", "email": "", "company": "asdf inc", "job_title": "NA", "phone": "", "state": "TX", "industry": "Software", "company_size": 5, "engagement_score": 1, "last_activity_date": "2026-02-15"},
        {"first_name": "Fake", "last_name": "Person", "email": "fake@gmail.com", "company": "none", "job_title": "N/A", "phone": "1234567", "state": "NY", "industry": "Retail", "company_size": 0, "engagement_score": 0, "last_activity_date": "2026-03-01"},
        {"first_name": "Spam", "last_name": "Lead", "email": "spam@spam.com", "company": "test", "job_title": "Bot", "phone": None, "state": "FL", "industry": "Marketing", "company_size": 2, "engagement_score": 0, "last_activity_date": "2026-04-12"},
        {"first_name": "Sample", "last_name": "Data", "email": "sample@sample.org", "company": "null", "job_title": "Null", "phone": None, "state": "CA", "industry": "SaaS", "company_size": 1, "engagement_score": 5, "last_activity_date": "2026-01-20"},
        {"first_name": "NoEmail", "last_name": "NoPhone", "email": None, "company": "Acme Test", "job_title": "Manager", "phone": None, "state": "WA", "industry": "Fintech", "company_size": 50, "engagement_score": 10, "last_activity_date": "2026-05-01"},
        {"first_name": "Robo", "last_name": "Bot", "email": "bot@botnet.xyz", "company": "dummy corp", "job_title": "Script", "phone": "111-111-1111", "state": "MA", "industry": "IT", "company_size": 1, "engagement_score": 0, "last_activity_date": "2026-02-01"},
        {"first_name": "Unknown", "last_name": "User", "email": "", "company": "xyz", "job_title": "", "phone": "", "state": "IL", "industry": "Consulting", "company_size": 5, "engagement_score": 0, "last_activity_date": "2026-03-22"},
        {"first_name": "Demo", "last_name": "Lead", "email": "demo@demo.com", "company": "testing 123", "job_title": "Demo", "phone": None, "state": "TX", "industry": "Software", "company_size": 10, "engagement_score": 3, "last_activity_date": "2026-06-10"}
    ]

    all_leads = base_records + duplicates + junk_rows
    random.shuffle(all_leads)
    
    df = pd.DataFrame(all_leads)
    return df.to_csv(index=False)
