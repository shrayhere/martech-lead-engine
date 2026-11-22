import os
import csv
import random

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)

def generate_messy_headers_csv():
    path = os.path.join(FIXTURES_DIR, "messy_headers.csv")
    headers = ["  FULL NAME  ", " E-MAIL  Address ", " ORG / Company ", "  Job Position  ", " TEL # ", "  Engagement %  "]
    rows = [
        ["  Priya Sharma ", "priya.s@novacloud.io", " NovaCloud Inc ", " VP of Sales ", " (415) 555-0101 ", " 92% "],
        [" Alex Rivera ", "alex.r@apextech.com", " Apex Tech ", " CTO ", " +1 212 555 0199 ", " 85 "],
        [" John Doe ", "john.d@acme.com", " Acme Corp ", " Director of Engineering ", " 555-0123 ", " 65 "],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print("Created messy_headers.csv")

def generate_1000_rows_csv():
    path = os.path.join(FIXTURES_DIR, "1000_rows.csv")
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    titles = ["CEO", "CTO", "VP Sales", "Director of IT", "Marketing Manager", "Account Executive", "Product Manager", "Software Engineer"]
    companies = ["NovaCloud", "ApexTech", "GlobalSys", "FinBridge", "DataVibe", "CloudScale", "PulsePoint", "NexusWave"]
    domains = ["novacloud.io", "apextech.com", "globalsys.com", "finbridge.com", "datavibe.io", "cloudscale.net"]

    rows = []
    for i in range(1, 1001):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        comp = random.choice(companies)
        dom = random.choice(domains)
        email = f"{fn.lower()}.{ln.lower()}{i}@{dom}"
        title = random.choice(titles)
        phone = f"+1 555 {random.randint(100,999)} {random.randint(1000,9999)}"
        state = random.choice(["CA", "NY", "TX", "FL", "IL", "WA"])
        eng = random.randint(10, 95)
        date = f"2026-10-{random.randint(1, 28):02d}"
        size = random.choice([25, 50, 150, 500, 2000])
        rows.append([fn, ln, email, comp, title, phone, state, eng, date, size])

    headers = ["First Name", "Last Name", "Email", "Company", "Job Title", "Phone", "State", "Engagement Score", "Last Activity Date", "Company Size"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print("Created 1000_rows.csv")

def generate_missing_columns_csv():
    path = os.path.join(FIXTURES_DIR, "missing_columns.csv")
    headers = ["First Name", "Last Name", "Email"]
    rows = [
        ["Alice", "Walker", "alice.walker@minimal.com"],
        ["Bob", "Vance", "bob.vance@vancerefrig.com"],
        ["Charlie", "Brown", "charlie.b@peanuts.com"],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print("Created missing_columns.csv")

def generate_out_of_range_values_csv():
    path = os.path.join(FIXTURES_DIR, "out_of_range_values.csv")
    headers = ["First Name", "Last Name", "Email", "Company", "Job Title", "Engagement Score", "Company Size", "Last Activity Date"]
    rows = [
        ["Over", "Score", "over.score@test.com", "Test Corp", "Analyst", "150", "-50", "2030-01-01"],
        ["Bad", "Date", "bad.date@test.com", "Test Corp", "Associate", "-20", "0", "1999-13-45"],
        ["Normal", "Lead", "normal@test.com", "Test Corp", "Manager", "75", "100", "2026-10-15"],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print("Created out_of_range_values.csv")

def generate_unusual_job_titles_csv():
    path = os.path.join(FIXTURES_DIR, "unusual_job_titles.csv")
    headers = ["First Name", "Last Name", "Email", "Company", "Job Title", "Engagement Score", "Company Size", "Last Activity Date"]
    rows = [
        ["Rajesh", "Patel", "rajesh@patelenterprises.com", "Patel Enterprises", "Owner & Proprietor", "80", "10", "2026-11-01"],
        ["Suresh", "Menon", "suresh@keralatrading.in", "Kerala Trading", "Managing Director", "85", "50", "2026-11-02"],
        ["Vikram", "Malhotra", "vikram@steelcorp.in", "Steel Corp", "Head - Sourcing & Procurement", "70", "500", "2026-11-03"],
        ["Anita", "Deshmukh", "anita@automotiveparts.in", "Auto Parts Co", "Procurement Head", "75", "250", "2026-11-04"],
        ["Rahul", "Verma", "rahul@startup.io", "Seed Startup", "Founder's Office Associate", "90", "15", "2026-11-05"],
        ["Kavita", "Rao", "kavita.intern@techlabs.com", "Tech Labs", "Summer Intern - Marketing", "95", "100", "2026-11-06"],
        ["Unknown", "Title", "unknown@mystery.com", "Mystery Co", "Grand Vizier of Synergy", "50", "100", "2026-11-07"],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print("Created unusual_job_titles.csv")

if __name__ == "__main__":
    generate_messy_headers_csv()
    generate_1000_rows_csv()
    generate_missing_columns_csv()
    generate_out_of_range_values_csv()
    generate_unusual_job_titles_csv()
    print("All fixtures generated successfully.")
