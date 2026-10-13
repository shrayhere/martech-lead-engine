from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.schemas import Rep, AssignmentLog
from app.services.assignment_service import seed_sales_reps, SEED_REPS

def assign_leads_in_memory(
    leads: List[Dict[str, Any]],
    db: Session,
    run_id: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes Sales Rep Automated 4-Tier Routing Engine in-memory for maximum throughput:
    Rule 1 (Highest): Territory Match AND Industry Match
    Rule 2: Territory Match Only
    Rule 3: Industry Specialty Match Only
    Rule 4: Round-Robin Load-Balancing (Lowest active assigned count)
    
    Returns:
      (assigned_leads, assignment_logs, stats)
    """
    seed_sales_reps(db)
    reps_db = db.query(Rep).all()
    
    # Track rep workloads in memory
    rep_list = []
    for r in reps_db:
        rep_list.append({
            "id": r.id,
            "name": r.name,
            "territories": [t.strip().upper() for t in r.territory.split(",")],
            "industry_specialty": r.industry_specialty.strip().lower(),
            "workload": 0
        })

    rule_counts = {
        "Rule 1 (Territory + Industry)": 0,
        "Rule 2 (Territory Only)": 0,
        "Rule 3 (Industry Only)": 0,
        "Rule 4 (Round-Robin Fallback)": 0
    }

    assignment_logs: List[Dict[str, Any]] = []

    for lead in leads:
        if lead.get("is_junk"):
            lead["assigned_rep_id"] = None
            lead["assignment_reason"] = "Junk record - unassigned"
            continue

        lead_state = (lead.get("state") or "").strip().upper()
        lead_ind = (lead.get("industry") or "").strip().lower()

        assigned_rep = None
        matched_rule = None
        reason = None

        # Rule 1: Territory AND Industry
        for rep in rep_list:
            terr_match = ("ALL" in rep["territories"]) or (lead_state in rep["territories"])
            ind_match = (rep["industry_specialty"] in lead_ind) or (lead_ind in rep["industry_specialty"])
            if terr_match and ind_match:
                assigned_rep = rep
                matched_rule = "Rule 1 (Territory + Industry)"
                reason = f"Assigned to {rep['name']}: territory match ({lead_state}) + industry match ({rep['industry_specialty']})"
                rule_counts[matched_rule] += 1
                break

        # Rule 2: Territory Only
        if not assigned_rep:
            for rep in rep_list:
                if lead_state in rep["territories"]:
                    assigned_rep = rep
                    matched_rule = "Rule 2 (Territory Only)"
                    reason = f"Assigned to {rep['name']}: territory match ({lead_state})"
                    rule_counts[matched_rule] += 1
                    break

        # Rule 3: Industry Only
        if not assigned_rep:
            for rep in rep_list:
                if rep["industry_specialty"] in lead_ind or lead_ind in rep["industry_specialty"]:
                    assigned_rep = rep
                    matched_rule = "Rule 3 (Industry Only)"
                    reason = f"Assigned to {rep['name']}: industry specialty match ({rep['industry_specialty']})"
                    rule_counts[matched_rule] += 1
                    break

        # Rule 4: Round-Robin Fallback (lowest workload)
        if not assigned_rep:
            rep_list.sort(key=lambda r: r["workload"])
            assigned_rep = rep_list[0]
            matched_rule = "Rule 4 (Round-Robin Fallback)"
            reason = f"Assigned to {assigned_rep['name']}: round-robin load balance (workload: {assigned_rep['workload']})"
            rule_counts[matched_rule] += 1

        assigned_rep["workload"] += 1
        lead["assigned_rep_id"] = assigned_rep["id"]
        lead["assignment_reason"] = reason

        assignment_logs.append({
            "run_id": run_id,
            "rep_id": assigned_rep["id"],
            "rule_matched": matched_rule,
            "reason": reason
        })

    # Update DB rep workload counts
    for rep in rep_list:
        db.query(Rep).filter(Rep.id == rep["id"]).update({Rep.assigned_lead_count: rep["workload"]})
    db.commit()

    stats = {
        "total_assigned": sum(rule_counts.values()),
        "rule_breakdown": rule_counts
    }

    return leads, assignment_logs, stats
