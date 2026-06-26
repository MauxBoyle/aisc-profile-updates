import os
import re
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import propose_account_role_swaps_for_single_account

load_dotenv()

print("🔌 Connecting to Salesforce Core Engine...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# =====================================================================
# 1. FETCH LIVE ACCOUNT ROLES, CONTACT DIRECTORY & LOCAL CASE CACHE
# =====================================================================
print("📡 Fetching live Account Junction details from Salesforce...")
acc_query = """
    SELECT Id, Name, 
           Cert_Certification_Contact__c, Cert_Principal_Contact__c, 
           Cert_Accounting_Contact__c, Cert_Marketing_contact__c
    FROM Account
"""
accounts_raw = sf.query_all(acc_query)
df_sf_accounts = pd.DataFrame(accounts_raw['records']).drop(columns='attributes', errors='ignore').set_index('Id')

print("📡 Fetching baseline Contact directory for lookup mappings...")
contacts_raw = sf.query_all("SELECT Id, FirstName, LastName, Email FROM Contact")
df_sf_contacts = pd.DataFrame(contacts_raw['records']).drop(columns='attributes', errors='ignore').set_index('Id')

# Create an instant Email-to-ContactID mapping dictionary
contact_email_to_id = {}
contact_email_to_name = {}
for c_id, row in df_sf_contacts.iterrows():
    email_clean = str(row.get('Email', '')).strip().lower()
    if email_clean:
        contact_email_to_id[email_clean] = c_id
        contact_email_to_name[email_clean] = f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip()

# Load the local case tracking history cache to locate Parent Cases
HISTORY_FILE = "pu_cases_1mhistory.csv"
if os.path.exists(HISTORY_FILE):
    print(f"💾 Loading Case historical mapping cache from '{HISTORY_FILE}'...")
    df_history = pd.read_csv(HISTORY_FILE).set_index('AccountId')
else:
    print(f"⚠️ Warning: '{HISTORY_FILE}' missing. Case logs will print to terminal only.")
    df_history = pd.DataFrame()

# =====================================================================
# 2. LOAD STAGED SUBMISSIONS
# =====================================================================
STAGING_FILE = 'staged_contact_updates.csv'
if not os.path.exists(STAGING_FILE):
    print(f"❌ '{STAGING_FILE}' not found. Please run your staging script first.")
    exit()

print(f"💾 Reading staged submissions from '{STAGING_FILE}'...")
df_staged = pd.read_csv(STAGING_FILE).fillna('')

for col in df_staged.columns:
    df_staged[col] = df_staged[col].astype(str).str.replace(r'^nan$', '', flags=re.IGNORECASE, regex=True).str.strip()

# =====================================================================
# 3. CONSOLIDATE & EXECUTE PROCESSOR
# =====================================================================
grouped_submissions = df_staged.groupby('Account__c')

roles_schema_map = {
    'Certification Contact': ('Cert_Email__c', 'Cert_Certification_Contact__c'),
    'Principal Contact': ('Principal_Email__c', 'Cert_Principal_Contact__c'),
    'Accounting Contact': ('AP_Email__c', 'Cert_Accounting_Contact__c'),
    'Quality Contact': ('Quality_Email__c', 'Cert_Marketing_contact__c')
}

print(f"\n🕵️‍♂️ Reconciling Account Roles and posting case audit feeds via centralized utils engine...\n")

for account_id, group in grouped_submissions:
    if account_id not in df_sf_accounts.index: continue
    
    sf_acc = df_sf_accounts.loc[account_id]
    account_name = sf_acc['Name']
    print(f"🏢 ACCOUNT: {account_name} [{account_id}]")
    
    # Call the centralized role matching engine
    res = propose_account_role_swaps_for_single_account(account_id, group, sf_acc, contact_email_to_id, contact_email_to_name, df_sf_contacts)
    
    pending_account_updates = {}
    case_chatter_logs = []

    # Handle Perfect Alignments
    for match in res['perfect_matches']:
        print(f"     🟢 {match}")

    # Handle Multiplicity Block Exceptions
    for conflict in res['multiplicity_conflicts']:
        err = f"🛑 ROLE UPDATE FAILURE [{conflict['Role']}]: Conflict detected. Multiple conflicting emails: {conflict['Emails']}."
        print(f"     {err}")
        case_chatter_logs.append(err)

    # Handle Missing Contact Id Warnings
    for unknown in res['unknown_emails']:
        err = f"⚠️ ROLE UPDATE FAILURE [{unknown['Role']}]: Email '{unknown['Email']}' does not map to any active Contact ID."
        print(f"     {err}")
        case_chatter_logs.append(err)

    # Queue Simple Substitutions
    for swap in res['proposed_swaps']:
        print(f"     ⚡ [{swap['Role']}]: Queueing update -> Assigning '{swap['Name']}'")
        pending_account_updates[swap['Field']] = swap['ContactId']
        case_chatter_logs.append(f"✅ ROLE UPDATE SUCCESS [{swap['Role']}]: Automatically assigned '{swap['Name']}'.")

    # =====================================================================
    # 4. COMMIT EXECUTION PASS TO SALESFORCE CORE
    # =====================================================================
    # Step A: Perform Live Account Field Updates if clear modifications exist
    if pending_account_updates:
        print(f"     💾 Writing live role field updates to Account record...")
        try:
            sf.Account.update(account_id, pending_account_updates)
            print("        🎉 Account updated successfully.")
        except Exception as e:
            print(f"        ❌ Failed to write update to Account: {e}")
            case_chatter_logs.append(f"❌ DATABASE ERROR: Failed to execute Account field update: {e}")

    # Step B: Log the Audit Trail to Case Chatter Feed
    if case_chatter_logs and target_case_id:
        chatter_payload = "\n".join(case_chatter_logs)
        # Format a clean system comment block block
        full_body = f"⚙️ AUTOMATED ACCOUNT ROLE UPDATE RUNTIME SUMMARY:\n{chatter_payload}"
        try:
            sf.FeedItem.create({'ParentId': target_case_id, 'Body': full_body})
            print(f"     📝 Posted runtime audit summary cleanly to Case ID {target_case_id} Chatter feed.")
        except Exception as e:
            print(f"     ❌ Failed to write Case Chatter log: {e}")
            
    print("-" * 60)
    print()
