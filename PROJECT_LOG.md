# 🗺️ Project Log & Automation Roadmap

**File Name:** `DESIGN_NOTES.md` / `ROADMAP.md`  
**Current State:** Submissions are cleanly staged into two localized files (`staged_key_updates.csv` and `staged_contact_updates.csv`). Standard case generation, internal text-block routing, and active Title backfill automations are fully baseline operational.

---

## 🚀 Active Roadmap & Future Improvements

### 1. Staging Layer Data Cleaners (Pre-Processing)
* **Title Spell-Check & Dictionary Standardization:** Intercept common corporate typos at the form submission level before they touch the evaluation engine. 
    * *Example caught in production:* `Chief Ficial Officer` ➡️ Auto-correct to `Chief Financial Officer`.
* **Role-Based "Email-Only" Vector Routing:** Expand horizontal backfill rules so that if a participant submits *only* an email address for a role, the script dynamically hunts the live Salesforce cache by email to backfill the missing First Name, Last Name, Title, and Phone parameters into the staging table.

### 2. Contact Reconciliation Heuristics (Comparison Layer)
* **Name Squashing (First + Middle Extensions):** Resolve false-positive name mismatches caused by middle names or initials stored natively inside Salesforce's `FirstName` field (or separate `MiddleName` API field) when a participant submits a combined string.
    * *Example caught in production:* Salesforce `FirstName` is `Jo` (with `Ann` in Middle Name or squashed), but participant submits `Jo Ann`. Implement a `.startswith()` prefix comparison test to auto-clear.
* **Salesforce Required Field Enforcement:** Ensure the system respects target schema validation requirements for net-new entries before generating Data Loader or direct API writing payloads.
    * *The "LastName" Requirement Rule:* Salesforce strictly requires a `LastName` for all Contacts. If a submission contains an anonymous role-based placeholder (e.g., `FirstName: Accounting`, `LastName: [Blank]`), the engine must auto-shift the data: `LastName = FirstName` and `FirstName = ""`.

### 3. Identity Resolution Architecture (Long-Term Value)
* **Email Heuristic Classification:** Differentiate between personal inbox addresses and corporate role/seat aliases to safely protect CRM data history.
    * *Personal Identifiers (`firstname.lastname@`):* High persistence accuracy. If names mismatch completely on an existing email, flag for a strict typo/spelling audit.
    * *Role/Seat Identifiers (`accounting@`, `qa@`, `purchasing@`):* High employee turnover probability. If a completely new name claims a role-based inbox address, interpret this as a *job transition* rather than a typo. Auto-archive the historical contact record and spawn a fresh, clean record for the new corporate seat-holder to protect historical data integrity.

---

## 🛠️ Current Operational Pipeline Summary

```text
    [Participant Portal Submissions]
                   │
                   ▼
       stage_profile_updates.py
    ┌──────────────┴──────────────┐
    ▼                             ▼
staged_key_updates.csv     staged_contact_updates.csv
(Facility & Narratives)    (Sanitized Roster Data)
    │                             │
    ▼                             ▼
generate_profile_cases_pu.py     update_contact_records.py
(Cuts Core Cases & Feeds)  (Auto-Patches Blank Titles)
                                  │
                                  ▼
                             [Data Loader Engine]
                             net_new_contacts.csv