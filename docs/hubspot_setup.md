# HubSpot sync and score-based workflow

The engine pushes cleaned, scored and classified leads into HubSpot as **contacts** (upsert by email).
Use a HubSpot **developer test account or practice portal**, not a production portal.

## 1. Create a private app (in HubSpot)

1. Settings → Integrations → **Private Apps** → *Create a private app* (name: `MarTech Lead Engine`).
2. Scopes:
   - `crm.objects.contacts.read`, `crm.objects.contacts.write`
   - `crm.schemas.contacts.read`, `crm.schemas.contacts.write` (to create the custom properties)
3. Create the app and copy the access token. Treat it like a password.

## 2. Give the token to the backend (never commit it)

Local (PowerShell, same window that starts uvicorn):

```powershell
$env:HUBSPOT_ACCESS_TOKEN = "<paste token here>"
```

Render: service `martech-lead-engine-api` → Environment → add `HUBSPOT_ACCESS_TOKEN`
(`render.yaml` declares it with `sync: false`, so Render asks for the value and it never lives in git).

The API only reports whether a token is set (`GET /api/hubspot/status`); it never returns the token.

## 3. Dry run, then push

In the app, open **HubSpot Sync**:

1. Pick the source (staged flow or a Smart Upload run).
2. **Preview (dry run)** shows how many contacts would be sent and the first five payloads. Nothing is sent.
3. **Push to HubSpot** (only enabled when a token is set) creates the property group and properties if needed,
   then upserts contacts in batches of 100 via `POST /crm/v3/objects/contacts/batch/upsert`.

Junk leads and leads without an email are never sent. Empty fields are left out, so the sync does not erase
values that already exist in HubSpot.

| HubSpot property | Source |
|---|---|
| `email`, `firstname`, `lastname`, `company`, `jobtitle`, `phone`, `state` | cleaned lead |
| `mle_lead_score` (number) | active score 0-100 |
| `mle_score_band` (dropdown Hot / Warm / Cold) | score band |
| `mle_persona`, `mle_buying_role`, `mle_interest` | AI classification |
| `mle_recommended_action` | business rules |
| `mle_assigned_rep` | rep routing |

All custom properties are in the property group **MarTech Lead Engine**.

## 4. Build the workflow on the score (in HubSpot)

Automation → Workflows → *Create workflow* → **Contact-based**, from scratch.

**Workflow A: Hot lead → sales**

- Enrollment trigger: `Lead Engine Band` **is any of** `Hot`. Turn on re-enrollment for that property.
- Actions:
  1. Set property `Lifecycle stage` = *Sales Qualified Lead*.
  2. Rotate record to owner (or set `Contact owner` from the rep in `Lead Engine Assigned Rep`).
  3. Create task for the contact owner: "Call within 24h: {{Lead Engine Next Action}}".
  4. Send internal email notification to the owner.

**Workflow B: Warm lead → nurture**

- Trigger: `Lead Engine Band` is `Warm`.
- Branch on `Lead Engine Buying Role`: *Decision Maker* → executive case-study sequence;
  otherwise → content nurture matched to `Lead Engine Interest`.

**Workflow C: Cold lead → newsletter**

- Trigger: `Lead Engine Band` is `Cold` → add to the newsletter list; re-check in 30 days.

Note: workflows need Marketing Hub / Sales Hub Professional or higher (developer test accounts include them).

## 5. Check it worked

- Contacts → filter `Lead Engine Band` = Hot: the count should match the Hot count in the app.
- Open one contact: the *MarTech Lead Engine* group shows score, band, persona, role, interest and next action.
- Push the same leads again: contacts are updated, not duplicated (upsert by email).
