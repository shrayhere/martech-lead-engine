from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.schemas import Rep, AssignmentLog
from app.services.assignment_service import seed_sales_reps
from app.utils.geo_utils import INDIA_TERRITORIES

def get_matching_territories(state: str, country: str) -> List[str]:
    results = []
    st_clean = (state or '').strip().upper()
    if st_clean:
        results.append(st_clean)

    # Check India territories
    if country == 'India' or any(st_clean in states for states in INDIA_TERRITORIES.values()):
        for region, states in INDIA_TERRITORIES.items():
            if st_clean in states or st_clean == region or f'INDIA - {region}' == st_clean:
                results.extend([f'INDIA - {region}', region, f'INDIA {region}'])

    return results

def assign_leads_in_memory(
    leads: List[Dict[str, Any]],
    db: Session,
    run_id: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    seed_sales_reps(db)
    reps_db = db.query(Rep).all()

    rep_list = []
    for r in reps_db:
        rep_list.append({
            'id': r.id,
            'name': r.name,
            'territories': [t.strip().upper() for t in r.territory.split(',')],
            'industry_specialty': r.industry_specialty.strip().lower(),
            'workload': 0
        })

    rule_counts = {
        'Rule 1 (Territory + Industry)': 0,
        'Rule 2 (Territory Only)': 0,
        'Rule 3 (Industry Only)': 0,
        'Rule 4 (Round-Robin Fallback)': 0
    }

    assignment_logs: List[Dict[str, Any]] = []

    for lead in leads:
        if lead.get('is_junk'):
            lead['assigned_rep_id'] = None
            lead['assignment_reason'] = 'Junk record - unassigned'
            continue

        lead_state = (lead.get('state') or '').strip().upper()
        lead_country = lead.get('country') or 'India'
        lead_ind = (lead.get('industry') or '').strip().lower()

        lead_terrs = get_matching_territories(lead_state, lead_country)

        assigned_rep = None
        matched_rule = None
        reason = None

        # Rule 1: Territory AND Industry
        for rep in rep_list:
            terr_match = ('ALL' in rep['territories']) or any(t in rep['territories'] for t in lead_terrs)
            ind_match = (rep['industry_specialty'] in lead_ind) or (lead_ind in rep['industry_specialty'])
            if terr_match and ind_match:
                assigned_rep = rep
                matched_rule = 'Rule 1 (Territory + Industry)'
                reason = f"Assigned to {rep['name']}: territory match ({lead_state or lead_country}) + industry match ({rep['industry_specialty']})"
                rule_counts[matched_rule] += 1
                break

        # Rule 2: Territory Only
        if not assigned_rep:
            for rep in rep_list:
                if any(t in rep['territories'] for t in lead_terrs):
                    assigned_rep = rep
                    matched_rule = 'Rule 2 (Territory Only)'
                    reason = f"Assigned to {rep['name']}: territory match ({lead_state or lead_country})"
                    rule_counts[matched_rule] += 1
                    break

        # Rule 3: Industry Only
        if not assigned_rep:
            for rep in rep_list:
                if (rep['industry_specialty'] in lead_ind) or (lead_ind in rep['industry_specialty']):
                    assigned_rep = rep
                    matched_rule = 'Rule 3 (Industry Only)'
                    reason = f"Assigned to {rep['name']}: industry specialty match ({rep['industry_specialty']})"
                    rule_counts[matched_rule] += 1
                    break

        # Rule 4: Round-Robin Load Balancing
        if not assigned_rep:
            assigned_rep = min(rep_list, key=lambda r: r['workload'])
            matched_rule = 'Rule 4 (Round-Robin Fallback)'
            reason = f"Assigned to {assigned_rep['name']}: round-robin load-balancing (workload: {assigned_rep['workload']})"
            rule_counts[matched_rule] += 1

        assigned_rep['workload'] += 1
        lead['assigned_rep_id'] = assigned_rep['id']
        lead['assignment_reason'] = reason

        assignment_logs.append({
            'run_id': run_id,
            'lead_id': None,
            'rep_id': assigned_rep['id'],
            'rule_matched': matched_rule,
            'reason': reason
        })

    # Update assigned counts in DB for each rep
    rep_workloads = {r['id']: r['workload'] for r in rep_list}
    for r in reps_db:
        r.assigned_lead_count = rep_workloads.get(r.id, 0)
    db.commit()

    stats = {
        'total_assigned': len([l for l in leads if not l.get('is_junk')]),
        'rule_breakdown': rule_counts
    }

    return leads, assignment_logs, stats
