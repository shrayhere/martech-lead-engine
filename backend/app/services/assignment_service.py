from sqlalchemy.orm import Session
from app.models.schemas import CleanLead, Rep, AssignmentLog

SEED_REPS = [
    {
        'name': 'Sarah Jenkins',
        'territory': 'CA, WA, OR, NV',
        'industry_specialty': 'SaaS'
    },
    {
        'name': 'Michael Chen',
        'territory': 'NY, MA, CT, NJ',
        'industry_specialty': 'Fintech'
    },
    {
        'name': 'David Rodriguez',
        'territory': 'TX, FL, GA, NC',
        'industry_specialty': 'Enterprise Technology'
    },
    {
        'name': 'Aarav Patel',
        'territory': 'INDIA - WEST, WEST, MAHARASHTRA, GUJARAT, MUMBAI, PUNE',
        'industry_specialty': 'Enterprise Technology'
    },
    {
        'name': 'Pooja Iyer',
        'territory': 'INDIA - SOUTH, SOUTH, KARNATAKA, TAMIL NADU, TELANGANA, BENGALURU, HYDERABAD',
        'industry_specialty': 'SaaS'
    },
    {
        'name': 'Rohan Sharma',
        'territory': 'INDIA - NORTH, NORTH, DELHI, HARYANA, PUNJAB, UTTAR PRADESH, NOIDA, GURUGRAM',
        'industry_specialty': 'Fintech'
    },
    {
        'name': 'Ananya Sen',
        'territory': 'INDIA - EAST, EAST, WEST BENGAL, ODISHA, BIHAR, KOLKATA',
        'industry_specialty': 'Healthcare IT'
    },
    {
        'name': 'James Wilson',
        'territory': 'ALL',
        'industry_specialty': 'Cybersecurity'
    }
]

def seed_sales_reps(db: Session):
    existing = db.query(Rep).count()
    if existing == 0:
        rep_objects = [
            Rep(
                name=r['name'],
                territory=r['territory'],
                industry_specialty=r['industry_specialty'],
                assigned_lead_count=0
            ) for r in SEED_REPS
        ]
        db.bulk_save_objects(rep_objects)
        db.commit()
    else:
        # Check if India reps need to be seeded into existing table
        names = {r.name for r in db.query(Rep).all()}
        new_reps = [
            Rep(
                name=r['name'],
                territory=r['territory'],
                industry_specialty=r['industry_specialty'],
                assigned_lead_count=0
            ) for r in SEED_REPS if r['name'] not in names
        ]
        if new_reps:
            db.bulk_save_objects(new_reps)
            db.commit()

def run_lead_assignment(db: Session) -> dict:
    """
    Executes Sales Rep Automated Routing Rules Engine across all clean, non-junk leads.
    
    ASSIGNMENT RULE PRIORITY ORDER:
    -------------------------------
    Rule 1 (Highest Priority): Direct Territory Match AND Industry Specialization Match.
      - Matches rep whose assigned territory list contains lead's state AND rep's industry specialty matches lead's industry.
    Rule 2: Direct Territory Match Only.
      - Matches rep whose territory list includes lead's normalized state.
    Rule 3: Industry Specialization Match Only.
      - Matches rep whose industry specialty matches lead's industry.
    Rule 4 (Fallback): Round-Robin / Workload Load-Balancing.
      - Assigns lead to the rep currently holding the lowest active assigned lead count.
    
    Stores human-readable assignment rationale string (e.g. 'Assigned to Rep Sarah Jenkins: territory match (CA) + industry match (SaaS)')
    in CleanLead.assignment_reason and logs in assignment_log.
    """
    seed_sales_reps(db)

    reps = db.query(Rep).all()
    if not reps:
        return {"error": "No sales reps found in database."}

    leads = db.query(CleanLead).filter(CleanLead.is_junk == False, CleanLead.run_id.is_(None)).all()
    if not leads:
        return {"error": "No clean leads available for assignment."}

    # Reset rep counts
    for rep in reps:
        rep.assigned_lead_count = 0

    assigned_count = 0
    rule1_count = 0
    rule2_count = 0
    rule3_count = 0
    rule4_count = 0

    assignment_logs = []

    for lead in leads:
        lead_state = (lead.state or "").strip().upper()
        lead_ind = (lead.industry or "").strip().lower()

        assigned_rep = None
        matched_rule_name = None
        reason = None

        # Rule 1: Territory Match AND Industry Match
        for rep in reps:
            rep_terr = [t.strip().upper() for t in rep.territory.split(",")]
            rep_ind = rep.industry_specialty.strip().lower()

            terr_match = ("ALL" in rep_terr) or (lead_state in rep_terr)
            ind_match = (rep_ind in lead_ind) or (lead_ind in rep_ind)

            if terr_match and ind_match:
                assigned_rep = rep
                matched_rule_name = "Rule 1: Territory + Industry Match"
                reason = f"Assigned to {rep.name}: territory match ({lead_state}) + industry match ({rep.industry_specialty})"
                rule1_count += 1
                break

        # Rule 2: Territory Match Only
        if not assigned_rep:
            for rep in reps:
                rep_terr = [t.strip().upper() for t in rep.territory.split(",")]
                if lead_state in rep_terr:
                    assigned_rep = rep
                    matched_rule_name = "Rule 2: Territory Match"
                    reason = f"Assigned to {rep.name}: territory match ({lead_state})"
                    rule2_count += 1
                    break

        # Rule 3: Industry Match Only
        if not assigned_rep:
            for rep in reps:
                rep_ind = rep.industry_specialty.strip().lower()
                if rep_ind in lead_ind or lead_ind in rep_ind:
                    assigned_rep = rep
                    matched_rule_name = "Rule 3: Industry Specialty Match"
                    reason = f"Assigned to {rep.name}: industry specialty match ({rep.industry_specialty})"
                    rule3_count += 1
                    break

        # Rule 4: Fallback Round-Robin (Lowest Lead Count)
        if not assigned_rep:
            reps.sort(key=lambda r: r.assigned_lead_count)
            assigned_rep = reps[0]
            matched_rule_name = "Rule 4: Round-Robin Fallback"
            reason = f"Assigned to {assigned_rep.name}: round-robin load balance (current workload: {assigned_rep.assigned_lead_count} leads)"
            rule4_count += 1

        # Apply assignment
        lead.assigned_rep_id = assigned_rep.id
        lead.assignment_reason = reason
        assigned_rep.assigned_lead_count += 1
        assigned_count += 1

        log_entry = AssignmentLog(
            lead_id=lead.id,
            rep_id=assigned_rep.id,
            rule_matched=matched_rule_name,
            reason=reason
        )
        assignment_logs.append(log_entry)

    db.query(AssignmentLog).filter(AssignmentLog.run_id.is_(None)).delete(synchronize_session=False)
    db.bulk_save_objects(assignment_logs)
    db.commit()

    return {
        "success": True,
        "total_leads_assigned": assigned_count,
        "rule_breakdown": {
            "Rule 1 (Territory + Industry)": rule1_count,
            "Rule 2 (Territory Only)": rule2_count,
            "Rule 3 (Industry Only)": rule3_count,
            "Rule 4 (Round-Robin Fallback)": rule4_count
        }
    }
