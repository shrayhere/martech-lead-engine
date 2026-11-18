# MarTech CRM: REST API

All endpoints are under `/api`, accept and return JSON (CSV exports excepted), and require a logged-in
session (cookie) except register/login. State-changing requests must send the CSRF token from the page's
`<meta name="csrf-token">` in an `X-CSRFToken` header.

**Errors** use a consistent shape and meaningful status codes:

```json
{ "error": "Please correct the highlighted contact fields.", "details": { "email": "Invalid email address." } }
```

`400` bad request · `401` not logged in · `404` not found (or owned by another user) · `409` conflict
(duplicate email/company, import already running/executed) · `413` file too large · `415` wrong file type ·
`422` validation failed · `500` unexpected error (imports are rolled back) · `503` database unavailable.

**Pagination:** list endpoints take `page` and `per_page` (max 100) and return
`{ items, page, per_page, total, pages }`.

## Authentication
| Method | Path | Body / notes |
|---|---|---|
| POST | `/api/auth/register` | `{full_name, email, password}` (password ≥ 8 chars with letter + number). First user becomes `admin`. |
| POST | `/api/auth/login` | `{email, password, remember?}`. Also refreshes time-based lead scores. |
| POST | `/api/auth/logout` | |
| GET | `/api/auth/me` | Current user |
| PUT | `/api/auth/profile` | `{full_name?, current_password?, new_password?}` |

## Contacts
| Method | Path | Notes |
|---|---|---|
| GET | `/api/contacts` | Filters: `q` (name, email, phone digits, job title, company name; partial & case-insensitive), `category` (`hot|warm|cold|excluded`), `company_id`, `no_company=1`, `lifecycle_stage`, `lead_status`, `lead_source`, `source_id`, `score_min`, `score_max`, `created_from`, `created_to`, `activity_from`, `activity_to`, `inactive_days`, `overridden=1`, `leads_only=1`. Sort: `sort=name|score|created|last_activity|company|updated`, `order=asc|desc`. |
| POST | `/api/contacts` | `{first_name, last_name?, email?, phone?, job_title?, lifecycle_stage?, lead_source?, company_id? \| new_company: {company_name, ...}}` |
| GET | `/api/contacts/<id>` | Contact, full company, activity timeline, score breakdown, recommended next action, audit history |
| PUT | `/api/contacts/<id>` | Partial update (same fields; `company_id: null` removes the association) |
| DELETE | `/api/contacts/<id>` | Deletes contact and its activities |
| POST | `/api/contacts/bulk` | `{ids:[...], action: set_category|clear_override|set_lifecycle|delete, value}` |
| GET | `/api/contacts/export` | CSV; accepts the same filters as the list |
| POST | `/api/contacts/<id>/activities` | `{activity_type, activity_date?, activity_description?}`; the score is recalculated |
| PUT | `/api/activities/<id>` | Edit an activity; the score is recalculated |
| DELETE | `/api/activities/<id>` | Remove an activity; the score is recalculated |

## Companies
| Method | Path | Notes |
|---|---|---|
| GET | `/api/companies` | `q`, `industry`, `country`, `has_contacts=0|1`, `sort=name|created|industry|contacts|hot`. Each item includes `contact_count`, `lead_count`, `distribution{hot,warm,cold}` (JOIN + GROUP BY). |
| POST | `/api/companies` | `{company_name, industry?, website?, company_email?, phone?, address?, city?, country?, employee_count?, annual_revenue?, description?}`. `409` if a company with the same normalised name exists. |
| GET | `/api/companies/<id>` | Company and its contacts |
| PUT | `/api/companies/<id>` | Partial update |
| DELETE | `/api/companies/<id>` | Contacts are kept, `company_id` becomes NULL |
| GET | `/api/companies/options?q=` | Lightweight list for searchable dropdowns |
| GET | `/api/companies/facets` | Distinct industries / countries |
| GET | `/api/companies/export` | CSV |

## Leads
| Method | Path | Notes |
|---|---|---|
| GET | `/api/leads` | Contacts in lead stages (subscriber → opportunity); same filters as contacts |
| GET | `/api/leads/<id>` | Same as contact detail |
| PUT | `/api/leads/<id>/category` | `{category: "hot"\|"warm"\|"cold"\|null, reason?}`. Sets or clears the manual override; the automatic category is kept and the change is audited |
| GET | `/api/leads/analytics` | Distribution, score bands, by-source stats, override/excluded counts |
| GET | `/api/leads/pipeline` | Kanban columns (top N per category + totals) |
| GET | `/api/leads/sources` | Distinct lead sources |

## CSV import & synchronisation
| Method | Path | Notes |
|---|---|---|
| POST | `/api/imports/upload` | multipart `file`. Validates type, size, binary content, encoding (UTF-8 / Windows-1252 / Latin-1) and delimiter. Returns `job`, `columns`, `preview` rows, `column_stats`, `suggested_mapping`. |
| GET | `/api/imports/fields` | Mappable CRM fields |
| POST | `/api/imports/preview` | `{import_id, mapping:{csv_column: field}, mode}`: **dry run**. Runs the full sync in a transaction that is rolled back; returns summary + row-by-row outcomes. |
| POST | `/api/imports/execute` | `{import_id, mapping, mode}` with `mode = insert_only|update_existing|upsert` (or `dry_run`). Runs in one transaction, writes reports, creates a sync log. `409` if another import for this user is running. |
| GET | `/api/imports/history` | Paginated import jobs |
| GET | `/api/imports/<id>` | Job + sync logs (+ columns/preview to resume an unexecuted upload) |
| GET | `/api/imports/<id>/report` | Job, sync logs, pending duplicate count; `?download=success|duplicates|errors` returns the CSV |
| GET | `/api/imports/<id>/errors` | Failed rows CSV (original values + reasons) |

## Data management
| Method | Path | Notes |
|---|---|---|
| GET | `/api/duplicates?status=pending|all|merged|...` | Review items with existing vs incoming values, field differences and a recommended action |
| POST | `/api/duplicates/scan` | Detect likely duplicates among stored contacts (phone, name + company, fuzzy name) |
| POST | `/api/duplicates/<id>/resolve` | `{action: keep_existing|update_existing|merge|not_duplicate}` |
| GET | `/api/duplicates/export` | CSV |
| GET | `/api/data-quality` | Quality checks, completeness, data sources |
| GET | `/api/search?q=` | Global search across contacts, companies and leads |
| GET | `/api/notifications` / POST `/api/notifications/read` | Import results, pending duplicates, leads turning hot |
| GET | `/api/activity-log` | Audit log (paginated, `entity_type` filter) |

## Dashboard & reports
| Method | Path | Notes |
|---|---|---|
| GET | `/api/dashboard/stats` | `range=all|today|7d|30d|90d|custom` (+ `start`, `end` for custom) |
| GET | `/api/dashboard/charts` | Distribution, leads over time (day/week buckets), contacts by company, lead sources, import history, funnel |
| GET | `/api/dashboard/recent` | Top leads, newest contacts, recent imports |
| GET | `/api/reports/summary` | Stats + charts + lead analytics + activity and industry breakdowns |
| GET | `/api/reports/imports.csv`, `/api/reports/activities.csv` | CSV exports |

## Settings
| Method | Path | Notes |
|---|---|---|
| GET | `/api/settings/scoring-rules` | Rules and category bands |
| PUT | `/api/settings/scoring-rules` | `{rules:[{activity_type, points}]}` or `{reset:true}`. Every lead is rescored. |
