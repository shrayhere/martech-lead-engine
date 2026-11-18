# Automation opportunity matrix (Project 3)

Which lead-operations tasks are worth automating, and in what order. Impact and effort are relative
ratings (High / Medium / Low) based on how often the task runs, how error-prone it is by hand, and how much
build work it needs. They are judgements, not measured time savings: no time study was done.

## Matrix

|  | **Low effort** | **High effort** |
|---|---|---|
| **High impact** | **Do first:** dedupe on exact email/phone · normalise state/phone · junk filter · rule-based scoring · territory routing · push to HubSpot | **Plan next:** fuzzy duplicate review queue · AI persona/role/interest labels · score-based HubSpot workflows · closed-loop model retraining |
| **Low impact** | **Quick wins:** CSV export by band · data-quality score report · sample data generator | **Avoid for now:** field-level merge (coalescing) · real-time enrichment from paid data vendors · custom BI dashboards |

## Task list

| # | Task (done by hand today) | Frequency | Error risk by hand | Impact | Effort | Status in this project |
|---|---|---|---|---|---|---|
| 1 | Remove exact duplicates (same email/phone) | Every import | High | High | Low | Automated (`/api/leads/clean`, pipeline) |
| 2 | Standardise states and phone numbers | Every import | High | High | Low | Automated (E.164, 2-letter codes) |
| 3 | Flag junk / placeholder rows | Every import | Medium | High | Low | Automated, with human confirm in the review queue |
| 4 | Decide whether two similar records are one person | Every import | High | High | Medium | Automated at 90%+; 80-90% goes to the review queue |
| 5 | Score leads Hot / Warm / Cold | Daily | Medium | High | Low | Automated (rules or ML) |
| 6 | Route leads to the right rep | Daily | Medium | High | Low | Automated (4-tier routing with rationale) |
| 7 | Label persona, buying role and interest | Daily | Medium | High | Medium | Automated (local model; optional Claude) |
| 8 | Pick the next action per lead | Daily | Medium | High | Medium | Automated (business rules) |
| 9 | Copy leads into HubSpot | Daily | High | High | Low | Automated (`/api/hubspot/sync`, upsert by email) |
| 10 | Create follow-up tasks for Hot leads | Daily | Medium | High | Medium | Configured in HubSpot workflows (`docs/hubspot_setup.md`) |
| 11 | Report data quality before/after | Weekly | Low | Medium | Low | Automated (Data-Quality Score page) |
| 12 | Export lead lists by band | Weekly | Low | Low | Low | Automated (`/api/leads/export`) |
| 13 | Re-tune scoring from won/lost deals | Quarterly | High | High | High | **Not automated** (needs CRM deal outcomes) |
| 14 | Merge conflicting fields from duplicates | Every import | Medium | Low | High | **Not automated** (winner-take-all by design) |
| 15 | Enrich missing firmographics (size, industry) | Every import | Medium | Medium | High | **Not automated** (needs a paid data vendor) |

## Recommended order

1. Keep the low-effort, high-impact items (1-3, 5, 6, 9) running on every import.
2. Staff the review queue (4, 3) for a few minutes a day; borderline merges are where silent data damage happens.
3. Turn on the HubSpot workflows (10) once the sync has run on a practice portal.
4. Next build: closed-loop retraining (13) once real won/lost outcomes exist; until then the scores are
   unvalidated against real conversions.
