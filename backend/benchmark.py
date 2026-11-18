import csv
import io
import os
import random
import tempfile
import time
from datetime import datetime, timedelta

# Benchmarks write thousands of rows: never point them at the main martech.db.
# Override with BENCHMARK_DATABASE_URL if you want to keep the results.
os.environ["DATABASE_URL"] = os.environ.get("BENCHMARK_DATABASE_URL") or     "sqlite:///" + os.path.join(tempfile.mkdtemp(prefix="martech_bench_"), "benchmark.db").replace("\\", "/")

from app.database import Base, engine  # noqa: E402  (must import after DATABASE_URL is set)
from app.services.pipeline_service import execute_smart_pipeline  # noqa: E402

Base.metadata.create_all(bind=engine)

FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
COMPANIES = ["Acme Corp", "TechFlow Inc", "Nexus Cloud", "Apex Global", "Starlight Systems", "Pinnacle Dynamics", "BlueWave Solutions", "Vanguard AI", "Summit Logic", "Axiom Bio"]
TITLES = ["CEO", "Chief Technology Officer", "VP of Sales", "VP of Engineering", "Director of IT", "Engineering Manager", "Account Executive", "Product Manager", "Lead Architect"]
INDUSTRIES = ["SaaS", "Software", "Fintech", "Healthcare IT", "Cybersecurity", "Cloud Computing", "Enterprise Technology", "Retail", "Manufacturing"]
STATES = ["CA", "NY", "TX", "FL", "IL", "WA", "MA", "GA", "NC", "MI", "OH", "PA"]

def generate_benchmark_csv(n_rows: int) -> bytes:
    """Generates synthetic CSV with realistic messy values and duplicates."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Full Name", "Company", "Job Title", "Email", "Phone", "State",
        "Industry", "Company Size", "Engagement", "Activity Date"
    ])

    base_date = datetime.now()

    for i in range(n_rows):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        full_name = f"{fn} {ln}"
        comp = random.choice(COMPANIES)
        domain = comp.lower().replace(" ", "").replace(".", "") + ".com"
        email = f"{fn.lower()}.{ln.lower()}{i % 15}@ {domain}".replace(" ", "")

        # Introduce some duplicates
        if i % 12 == 0 and i > 0:
            email = f"duplicate_lead_{i % 5}@{domain}"
            full_name = f"Duplicate User {i % 5}"

        # Messy formats: phone numbers, company size strings
        phone_formats = [
            f"+1{random.randint(200,999)}{random.randint(100,999)}{random.randint(1000,9999)}",
            f"({random.randint(200,999)}) {random.randint(100,999)}-{random.randint(1000,9999)}",
            f"{random.randint(200,999)}.{random.randint(100,999)}.{random.randint(1000,9999)}"
        ]
        phone = random.choice(phone_formats)

        size_formats = [
            f"{random.randint(50, 500)}",
            f"~{random.randint(100, 1000)}",
            f"1k+",
            f"50-200",
            f"{random.randint(1, 10)}k"
        ]
        cs = random.choice(size_formats)

        eng = random.randint(10, 99)
        days_ago = random.randint(1, 90)
        act_date = (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        writer.writerow([
            full_name, comp, random.choice(TITLES), email, phone,
            random.choice(STATES), random.choice(INDUSTRIES), cs, eng, act_date
        ])

    return out.getvalue().encode("utf-8")

def run_benchmark():
    print("=" * 70)
    print(" MarTech Lead Engine - End-to-End Smart Pipeline Performance Benchmark")
    print("=" * 70)

    # ----------------------------------------------------
    # TEST 1: 1,000 Rows Benchmark (Target: < 2.0s)
    # ----------------------------------------------------
    print("\n[TEST 1] Generating 1,000 synthetic rows...")
    csv_1k = generate_benchmark_csv(1000)

    print("Running end-to-end pipeline (Parse > Map > Clean > Dedupe > Score > Assign > DB)...")
    t0 = time.perf_counter()
    result_1k = execute_smart_pipeline(csv_1k, "benchmark_1000.csv")
    duration_1k = time.perf_counter() - t0

    t_1k = result_1k["timings"]
    print(f"\n>> 1,000 ROWS COMPLETED IN: {duration_1k:.3f} seconds (Target: < 2.0s)")
    print(f"   - Parse:          {t_1k.get('parse_ms', 0):>8.1f} ms")
    print(f"   - Map:            {t_1k.get('map_ms', 0):>8.1f} ms")
    print(f"   - Clean:          {t_1k.get('clean_ms', 0):>8.1f} ms")
    print(f"   - Dedupe:         {t_1k.get('dedupe_ms', 0):>8.1f} ms")
    print(f"   - Score:          {t_1k.get('score_ms', 0):>8.1f} ms")
    print(f"   - Assign:         {t_1k.get('assign_ms', 0):>8.1f} ms")
    print(f"   - DB Bulk Save:   {t_1k.get('db_bulk_persist_ms', 0):>8.1f} ms")
    print(f"   - Total Reported: {t_1k.get('total_ms', 0):>8.1f} ms")
    print(f"   - Clean Leads Out: {result_1k['summary']['rows_out']}")
    print(f"   - Duplicates:      {result_1k['summary']['duplicates_merged']}")

    status_1k = "PASS" if duration_1k < 2.0 else "WARN"
    print(f"   [RESULT 1,000 ROWS]: {status_1k} ({duration_1k:.3f}s < 2.0s)")
    assert duration_1k < 2.0, f"Benchmark failed: 1,000 rows took {duration_1k:.2f}s (exceeded 2.0s target)"

    # ----------------------------------------------------
    # TEST 2: 10,000 Rows Benchmark (Target: < 10.0s)
    # ----------------------------------------------------
    print("\n[TEST 2] Generating 10,000 synthetic rows...")
    csv_10k = generate_benchmark_csv(10000)

    print("Running end-to-end pipeline (Parse > Map > Clean > Dedupe > Score > Assign > DB)...")
    t0 = time.perf_counter()
    result_10k = execute_smart_pipeline(csv_10k, "benchmark_10000.csv")
    duration_10k = time.perf_counter() - t0

    t_10k = result_10k["timings"]
    print(f"\n>> 10,000 ROWS COMPLETED IN: {duration_10k:.3f} seconds (Target: < 10.0s)")
    print(f"   - Parse:          {t_10k.get('parse_ms', 0):>8.1f} ms")
    print(f"   - Map:            {t_10k.get('map_ms', 0):>8.1f} ms")
    print(f"   - Clean:          {t_10k.get('clean_ms', 0):>8.1f} ms")
    print(f"   - Dedupe:         {t_10k.get('dedupe_ms', 0):>8.1f} ms")
    print(f"   - Score:          {t_10k.get('score_ms', 0):>8.1f} ms")
    print(f"   - Assign:         {t_10k.get('assign_ms', 0):>8.1f} ms")
    print(f"   - DB Bulk Save:   {t_10k.get('db_bulk_persist_ms', 0):>8.1f} ms")
    print(f"   - Total Reported: {t_10k.get('total_ms', 0):>8.1f} ms")
    print(f"   - Clean Leads Out: {result_10k['summary']['rows_out']}")
    print(f"   - Duplicates:      {result_10k['summary']['duplicates_merged']}")

    status_10k = "PASS" if duration_10k < 10.0 else "WARN"
    print(f"   [RESULT 10,000 ROWS]: {status_10k} ({duration_10k:.3f}s < 10.0s)")
    assert duration_10k < 10.0, f"Benchmark failed: 10,000 rows took {duration_10k:.2f}s (exceeded 10.0s target)"

    print("\n" + "=" * 70)
    print(" ALL PERFORMANCE TARGETS SATISFIED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_benchmark()
