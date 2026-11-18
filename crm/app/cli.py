"""Flask CLI commands: `flask seed`, `flask rescore`."""
import random
from datetime import timedelta

import click

from app.extensions import db
from app.models import Company, Contact, LeadActivity, User
from app.models.base import utcnow
from app.services import crm, lead_scoring
from app.services.data_cleaner import company_key

DEMO_EMAIL = "demo@martech.local"
DEMO_PASSWORD = "MarTechDemo2026"

SEED_COMPANIES = [
    ("Google", "Technology", "google.com", "Bengaluru", "India", 180000, 280_000_000_000),
    ("Infosys", "IT Services", "infosys.com", "Bengaluru", "India", 340000, 18_000_000_000),
    ("HubWave Analytics", "SaaS", "hubwave.io", "Pune", "India", 220, 14_000_000),
    ("Northwind Traders", "Retail", "northwind.com", "Seattle", "United States", 1200, 310_000_000),
    ("Acme Fintech", "Fintech", "acmefintech.com", "Mumbai", "India", 650, 52_000_000),
    ("BluePeak Health", "Healthcare", "bluepeakhealth.com", "Boston", "United States", 2400, 640_000_000),
    ("Cyberdyne Security", "Cybersecurity", "cyberdyne.io", "Austin", "United States", 340, 41_000_000),
    ("GreenLeaf Logistics", "Logistics", "greenleaf.co", "Chennai", "India", 1800, 120_000_000),
    ("Orbit Media", "Media", "orbitmedia.com", "London", "United Kingdom", 90, 8_500_000),
    ("Zenith Manufacturing", "Manufacturing", "zenithmfg.com", "Stuttgart", "Germany", 5200, 900_000_000),
    ("EduSpark Learning", "Education", "eduspark.in", "New Delhi", "India", 140, 6_000_000),
    ("Quantum Retail Labs", "SaaS", "quantumretail.ai", "Singapore", "Singapore", 75, 4_200_000),
]

FIRST = ["Rahul", "Aman", "Priya", "Sneha", "Arjun", "Kavya", "Rohan", "Ananya", "Vikram", "Isha", "Karan",
         "Meera", "John", "Emily", "Michael", "Sarah", "David", "Laura", "Daniel", "Olivia", "James", "Sophia",
         "Liam", "Emma", "Noah", "Ava", "Lucas", "Mia", "Ethan", "Chloe", "Aditya", "Neha", "Siddharth", "Pooja",
         "Ravi", "Tara"]
LAST = ["Sharma", "Verma", "Singh", "Patel", "Iyer", "Reddy", "Gupta", "Nair", "Mehta", "Kapoor", "Rao",
        "Joshi", "Smith", "Johnson", "Brown", "Miller", "Wilson", "Taylor", "Anderson", "Thomas", "Moore",
        "Martin", "Clark", "Lewis", "Walker", "Hall", "Young", "King", "Wright", "Scott", "Bose", "Desai",
        "Malhotra", "Chopra", "Kulkarni", "Menon"]
TITLES = ["Marketing Manager", "Sales Executive", "HR Manager", "VP of Marketing", "Chief Technology Officer",
          "Head of Growth", "Product Manager", "Director of Sales", "Procurement Lead", "Operations Manager",
          "CEO", "Data Analyst"]
SOURCES = ["Website", "LinkedIn", "Referral", "Webinar", "Trade Show", "Google Ads", "Email Campaign"]
STAGES = ["subscriber", "lead", "lead", "lead", "mql", "mql", "sql", "opportunity", "customer"]

# Activity "profiles" produce a realistic Hot/Warm/Cold mix.
PROFILES = {
    "hot": [("demo_requested", 3), ("pricing_inquiry", 5), ("email_clicked", 8), ("website_visit", 9)],
    "hot2": [("meeting_scheduled", 2), ("form_submitted", 6), ("brochure_downloaded", 10), ("email_opened", 12)],
    "warm": [("form_submitted", 6), ("brochure_downloaded", 9), ("email_opened", 15)],
    "warm2": [("email_clicked", 4), ("website_visit", 11), ("website_visit", 18)],
    "cold": [("email_opened", 20)],
    "stale": [("demo_requested", 70), ("email_opened", 75)],
    "none": [],
}
PROFILE_CYCLE = ["hot", "warm", "cold", "hot2", "warm2", "stale", "warm", "cold", "none", "hot", "warm2", "cold"]


def seed_user(user, rng=None):
    rng = rng or random.Random(42)
    now = utcnow()
    source = crm.get_source(user.user_id, "Seed data", "seed", "Demonstration records created by `flask seed`.")
    lead_scoring.ensure_default_rules(user.user_id)
    companies = []
    for i, (name, industry, domain, city, country, emp, rev) in enumerate(SEED_COMPANIES):
        key = company_key(name)
        company = Company.query.filter_by(owner_id=user.user_id, name_key=key).first()
        if not company:
            company = Company(owner_id=user.user_id, company_name=name, name_key=key, industry=industry,
                              website=f"https://{domain}", company_email=f"info@{domain}",
                              phone=f"+1555{1000000 + i * 7919:07d}"[:12], city=city, country=country,
                              employee_count=emp, annual_revenue=rev,
                              description=f"{name} is a {industry.lower()} company headquartered in {city}.",
                              created_at=now - timedelta(days=rng.randint(20, 120)))
            db.session.add(company)
        companies.append(company)
    db.session.flush()

    created = 0
    for i in range(36):
        first, last = FIRST[i], LAST[i]
        # Google gets the three contacts from the specification example; others are spread out.
        if i < 3:
            company = companies[0]
            first, last = [("Rahul", "Sharma"), ("Aman", "Verma"), ("Priya", "Singh")][i]
            title = ["Marketing Manager", "Sales Executive", "HR Manager"][i]
        else:
            company = None if i % 11 == 10 else companies[i % len(companies)]
            title = TITLES[i % len(TITLES)]
        domain = company.website.replace("https://", "") if company else "gmail.com"
        email = f"{first.lower()}.{last.lower()}@{domain}"
        if Contact.query.filter_by(owner_id=user.user_id, email=email).first():
            continue
        contact = Contact(
            owner_id=user.user_id, first_name=first, last_name=last, email=email,
            phone=f"+9198{rng.randint(10000000, 99999999)}" if i % 3 else f"+1415{rng.randint(1000000, 9999999)}",
            job_title=title, company_id=company.company_id if company else None,
            lifecycle_stage=STAGES[i % len(STAGES)], lead_source=SOURCES[i % len(SOURCES)], lead_status="open",
            created_at=now - timedelta(days=rng.randint(0, 85), hours=rng.randint(0, 23)),
        )
        db.session.add(contact)
        db.session.flush()
        contact.sources.append(source)
        for activity_type, days_ago in PROFILES[PROFILE_CYCLE[i % len(PROFILE_CYCLE)]]:
            db.session.add(LeadActivity(contact_id=contact.contact_id, activity_type=activity_type,
                                        activity_description="Seed activity",
                                        activity_date=now - timedelta(days=days_ago, hours=rng.randint(0, 12))))
        created += 1
    db.session.flush()
    lead_scoring.recalculate_owner(user.user_id)
    return created


def register_cli(app):
    @app.cli.command("seed")
    @click.option("--email", default=DEMO_EMAIL, show_default=True)
    @click.option("--password", default=DEMO_PASSWORD, show_default=True)
    @click.option("--name", default="Demo User", show_default=True)
    def seed(email, password, name):
        """Create a demo user (if needed) with 12 companies, 36 contacts and activities."""
        from app.routes.auth import bootstrap_user
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(full_name=name, email=email, role="admin" if User.query.count() == 0 else "member")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            bootstrap_user(user)
            click.echo(f"Created user {email}")
        created = seed_user(user)
        db.session.commit()
        click.echo(f"Seeded {created} contacts across {len(SEED_COMPANIES)} companies for {email}.")

    @app.cli.command("rescore")
    def rescore():
        """Recalculate every lead score (e.g. daily, so 30-day inactivity penalties apply)."""
        for user in User.query.all():
            lead_scoring.recalculate_owner(user.user_id)
        db.session.commit()
        click.echo("All lead scores recalculated.")
