# Deduplication evaluation

Dataset: `generate_sample_leads(200)` (seed 42): 200 rows, 20 planted duplicate pairs.
A *wrong merge* joins two different people; a *missed duplicate* leaves a planted pair unmerged.

| Rule | Threshold | Correct merges | Wrong merges | Missed duplicates | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Old (composite only) | 75% | 20 | 57 | 0 | 26% | 100% |
| Old (composite only) | 80% | 20 | 33 | 0 | 38% | 100% |
| Old (composite only) | 85% | 20 | 20 | 0 | 50% | 100% |
| Old (composite only) | 90% | 20 | 1 | 0 | 95% | 100% |
| Old (composite only) | 95% | 20 | 0 | 0 | 100% | 100% |
| New (guarded) | 75% | 20 | 0 | 0 | 100% | 100% |
| New (guarded) | 80% | 20 | 0 | 0 | 100% | 100% |
| New (guarded) | 85% | 20 | 0 | 0 | 100% | 100% |
| New (guarded) | 90% | 20 | 0 | 0 | 100% | 100% |
| New (guarded) | 95% | 20 | 0 | 0 | 100% | 100% |

## Examples of wrong merges made by the old rule at 85%

* reese martinez (CloudScale Dynamics) <-> Rowan Martin (CloudScale Dynamics): composite similarity 86.5%
* Christopher Miller (Horizon Financial) <-> Christopher Thomas (Horizon Financial): composite similarity 87.5%
* Pat Jackson (Cybershield Enterprise) <-> Pat Brown (Cybershield Enterprise): composite similarity 85.1%
* Rowan Martin (DataPulse Systems) <-> Rowan Brown (DataPulse Systems): composite similarity 85.1%
* Jonathan Jackson (HyperGrowth Marketing) <-> Jordan Johnson (HyperGrowth Marketing): composite similarity 85.4%
* Katherine Thomas (OmniChannel Media) <-> Katherine Wilson (OmniChannel Media): composite similarity 86.8%
* Sam Anderson (Peak Performance SaaS) <-> Sam Martin (Peak Performance SaaS Inc): composite similarity 86.7%
* Sam Anderson (Peak Performance SaaS) <-> Sam Martin (Peak Performance SaaS): composite similarity 89.0%
* Sam Martin (Peak Performance SaaS Inc) <-> Sam Anderson (Peak Performance SaaS Inc): composite similarity 85.7%
* Morgan Wilson (CyberShield Enterprise) <-> Morgan Williams (CyberShield Enterprise): composite similarity 92.7%

## Real merges made by the new rule at 85% (from the merge log)

20 merges: 20 by exact email/phone match, 0 by the guarded fuzzy rule. On this dataset every planted duplicate still shares an email or phone with its original, so the fuzzy path is exercised separately by unit tests (tests/test_dedup_rules.py).

| Archived record | Kept record | Score | Reason |
|---|---|---:|---|
| reese martinez (CloudScale Dynamics) | Reese Martinez (CloudScale Dynamics) | 100.0% | Exact match on email address (reese.martinez@cloudscaledynamics.com) |
| Taylor Martin (Elevate Health) | Taylor Martin (Elevate Health) | 100.0% | Exact match on E.164 phone number (+17097973344) |
| Alexander Rodriguez (DataPulse Systems) | Alexander Rodriguez (DataPulse Systems Inc) | 100.0% | Exact match on email address (alexander.rodriguez@datapulsesystems.com) |
| Sam Anderson (Peak Performance SaaS) | Sam Anderson (Peak Performance SaaS Inc) | 100.0% | Exact match on email address (sam.anderson@peakperformancesaas.com) |
| Emersom Wilson (CloudScale Dynamics) | Emerson Wilson (CloudScale Dynamics) | 100.0% | Exact match on email address (emerson.wilson@cloudscaledynamics.com) |
| Sam Martin (Peak Performance SaaS Inc) | Sam Martin (Peak Performance SaaS) | 100.0% | Exact match on email address (sam.martin@peakperformancesaas.com) |
| Elizabeth Davis (Apex Global) | Elizabethn Davis (Apex Global) | 100.0% | Exact match on email address (elizabeth.davis@apexglobal.com) |
| Emerson Johnson (CyberShield Enterprise) | Emerson Johnson (CyberShield Enterprise) | 100.0% | Exact match on E.164 phone number (+16622381932) |
| Quinn Davis (Apex Global) | quinn davis (Apex Global) | 100.0% | Exact match on email address (quinn.davis@apexglobal.com) |
| Skyler Jackson (DataPulse Systems Inc) | Skyler Jackson (DataPulse Systems) | 100.0% | Exact match on email address (skyler.jackson@datapulsesystems.com) |
| Jonathan Williams (Horizon Financial) | Jonathan Williams (Horizon Financial) | 100.0% | Exact match on E.164 phone number (+14534041333) |
| elizabeth davis (Omnichannel Media) | Elizabeth Davis (Omnichannel Media) | 100.0% | Exact match on email address (elizabeth.davis@omnichannelmedia.com) |
| Finley Williams (Acme CORP) | Finley Williams (ACME CORP Inc) | 100.0% | Exact match on email address (finley.williams@acmecorp.com) |
| Pat Brown (TechFlow Inc) | Pat Brown (TechFlow Inc) | 100.0% | Exact match on E.164 phone number (+16206781887) |
| Alexander Davis (CyberShield Enterprise) | Alexander Davis (CyberShield Enterprise) | 100.0% | Exact match on E.164 phone number (+12804564216) |
| Jonathan Brown (Acme Corp) | Jonatham Brown (Acme Corp) | 100.0% | Exact match on email address (jonathan.brown@acmecorp.com) |
| Samanthan Gonzalez (DataPulse Systems) | Samantha Gonzalez (DataPulse Systems) | 100.0% | Exact match on email address (samantha.gonzalez@datapulsesystems.com) |
| Reese Johnson (Datapulse Systems) | reese johnson (Datapulse Systems) | 100.0% | Exact match on email address (reese.johnson@datapulsesystems.com) |
| Morgam Rodriguez (CloudScale Dynamics) | Morgan Rodriguez (CloudScale Dynamics) | 100.0% | Exact match on email address (morgan.rodriguez@cloudscaledynamics.com) |
| Benjamin Martin (Horizon Financial) | benjamin martin (Horizon Financial) | 100.0% | Exact match on email address (benjamin.martin@horizonfinancial.com) |
