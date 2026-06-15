import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import is_valid_explanation, create_history_cache_row

load_dotenv()

# --- CONFIGURABLE GLOBAL VARIABLES ---
PRIMARY_RESPONDER_ID = "005f200000A06i6AAB"  # MB User ID
CERTIFICATION_QUEUE_ID = "00Gf2000005cagqEAA"  # Certification Queue ID
HISTORY_FILE = "pu_cases_1mhistory.csv"

# Establish Connection
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# =====================================================================
# 1. DATA INGESTION & LOCAL CACHE LOOKUPS
# =====================================================================
print("📡 Fetching baseline Salesforce records (Accounts & Contacts)...")

acc_query = """
    SELECT Id, Name, Certification_ID__c, BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry,
           Cert_Certification_Contact__c, Cert_Principal_Contact__c, Cert_Accounting_Contact__c, Cert_Marketing_contact__c
    FROM Account
"""
accounts_raw = sf.query_all(acc_query)
df_accounts = pd.DataFrame(accounts_raw['records']).drop(columns='attributes', errors='ignore').set_index('Id')

contacts_raw = sf.query_all("SELECT Id, FirstName, LastName, Email, AccountId, Title, Phone FROM Contact")
df_contacts = pd.DataFrame(contacts_raw['records']).drop(columns='attributes', errors='ignore').set_index('Id')

# Build the Pythonic Contact Role Map Dictionary
account_role_map = {}
for acc_id, row in df_accounts.iterrows():
    account_role_map[acc_id] = {
        'Certification': row.get('Cert_Certification_Contact__c'),
        'Principal': row.get('Cert_Principal_Contact__c'),
        'Accounting': row.get('Cert_Accounting_Contact__c'),
        'Quality': row.get('Cert_Marketing_contact__c')
    }

# Load local case history tracking file
try:
    df_history = pd.read_csv(HISTORY_FILE)
except FileNotFoundError:
    print(f"⚠️ '{HISTORY_FILE}' missing. Instantiating fresh tracking sheet.")
    df_history = pd.DataFrame(columns=['Id', 'Case.Name', 'ContactId', 'AccountId', 'Status', 'Subject', 'CreatedDate', 'LastModifiedDate'])

# --- CHANGED: READ FROM PRISTINE LOCAL STAGING CSV TABLES ---
print("💾 Loading sanitized data from local staging tables...")
df_key_updates = pd.read_csv('staged_key_updates.csv') if os.path.exists('staged_key_updates.csv') else pd.DataFrame()
df_contact_updates = pd.read_csv('staged_contact_updates.csv') if os.path.exists('staged_contact_updates.csv') else pd.DataFrame()

if df_key_updates.empty and df_contact_updates.empty:
    print("🏁 No staged updates found on disk to process. Exiting smoothly.")
    exit()

# Combine both staging dataframes into a master processing stack for routing
df_pus = pd.concat([df_key_updates, df_contact_updates], ignore_index=True).drop_duplicates(subset=['Id'])

# =====================================================================
# 3. HELPER FUNCTION: TEXT BLOCK GENERATOR ENGINE (REWRITTEN)
# =====================================================================
def build_comment_blocks(pu_records_list, account_id, multi_note=None):
    acc_row = df_accounts.loc[account_id]
    blocks = []
    
    # --- TEXT BLOCK 00: MINUTE-LEVEL SYSTEM RUNTIME HEADER ---
    # Generates: "PROFILE UPDATE PU-XXXXX RECEIVED YYYY-MM-DD HH:MM"
    pu_number = first_row.get('Name', 'UNKNOWN_PU')
    submission_time = first_row.get('CreatedDate', datetime.today().strftime('%Y-%m-%d %H:%M'))
    
    system_header = f"🚨 PROFILE UPDATE {pu_number} RECEIVED {submission_time} 🚨"
    blocks.append(system_header)

    # 1. Submitter details block
    first_row = pu_records_list[0]
    submitter_email = str(first_row.get('Email__c', '')).strip().lower()
    matched_contact = df_contacts[df_contacts['Email'].str.lower() == submitter_email]
    
    if matched_contact.empty:
        blocks.append(f"👤 UNMATCHED SUBMITTER DETAILS:\nName: {first_row.get('Name__c')}\nEmail: {first_row.get('Email__c')}")

    if multi_note:
        blocks.append(multi_note)
        
    # 2. Courtesy Block
    blocks.append(f"Thank you for updating your information with AISC. The changes are summarized below. An updated Participant Portal login will be sent by a separate email, if needed. Unless otherwise noted, previous contacts will remain in the {acc_row['Name']} contact list.")
    
    combined_key_updates = []
    has_key_data_changes = False
    
    for r in pu_records_list:
        eff_date = r.get('Effective_Date__c') or datetime.today().strftime('%Y-%m-%d')
        
        # Check Facility Address changes
        if pd.notnull(r.get('Revised_Facility_Street__c')) and str(r.get('Revised_Facility_Street__c')).strip() != "":
            has_key_data_changes = True
            combined_key_updates.append(
                f"\nFacility Address: {r.get('Revised_Facility_Street__c','')}, {r.get('Revised_Facility_City__c','')}, {r.get('Revised_Facility_State__c','')} {r.get('Revised_Facility_Zip__c','')} {r.get('Revised_Facility_Country__c','')}\n"
                f"  replaces {acc_row.get('BillingStreet','')}, {acc_row.get('BillingCity','')}, {acc_row.get('BillingState','')} {acc_row.get('BillingPostalCode','')} {acc_row.get('BillingCountry','')}\n"
                f"Effective {eff_date}"
            )
        # Check Company Name
        if pd.notnull(r.get('Revised_Company_Name__c')) and str(r.get('Revised_Company_Name__c')).strip() != "":
            has_key_data_changes = True
            combined_key_updates.append(f"\nOwnership: {r.get('Revised_Company_Name__c','')}\n  replaces {acc_row['Name']}\nEffective {eff_date}")
            
        # Check Company Owner
        if pd.notnull(r.get('Revised_Company_Owner__c')) and str(r.get('Revised_Company_Owner__c')).strip() != "":
            has_key_data_changes = True
            combined_key_updates.append(f"\nOwnership Owner Field: {r.get('Revised_Company_Owner__c','')}\nEffective {eff_date}")

        # Inject Pre-compiled Narrative Bullet Blocks from Staging
        if pd.notnull(r.get('Narrative_Questions_Block__c')) and str(r.get('Narrative_Questions_Block__c')).strip() != "":
            has_key_data_changes = True
            combined_key_updates.append(f"\nPROMPTED PROGRAM CHANGES:\n{r.get('Narrative_Questions_Block__c')}")

    if has_key_data_changes and combined_key_updates:
        blocks.append("\n".join(combined_key_updates))
        
    # 3. Contacts Block: COMPACT COMMA-SEPARATED LAYOUT (UPDATED)
    contact_updates_str = ""
    roles_map = {
        'Cert Contact': ('Cert_First_Name__c', 'Cert_Last_Name__c', 'Cert_Title__c', 'Cert_Email__c', 'Cert_Phone__c', 'Certification'),
        'Principal Contact': ('Principal_First_Name__c', 'Principal_Last_Name__c', 'Principal_Title__c', 'Principal_Email__c', 'Principal_Phone__c', 'Principal'),
        'AP Contact': ('AP_First_Name__c', 'AP_Last_Name__c', 'AP_Title__c', 'AP_Email__c', 'AP_Phone__c', 'Accounting'),
        'Quality Contact': ('Quality_First_Name__c', 'Quality_Last_Name__c', 'QC_Title__c', 'Quality_Email__c', 'Quality_Phone__c', 'Quality')
    }
    
    for r in pu_records_list:
        for role_label, fields in roles_map.items():
            new_email = r.get(fields[3])
            if pd.notnull(new_email) and str(new_email).strip() != "":
                
                # Fetch current live database value for comparison context
                current_contact_id = account_role_map.get(account_id, {}).get(fields[5])
                if current_contact_id and current_contact_id in df_contacts.index:
                    con_row = df_contacts.loc[current_contact_id]
                    replaces_str = f"{con_row.get('FirstName','') or ''} {con_row.get('LastName','') or ''}, {con_row.get('Title','') or 'No Title'}, {con_row.get('Email','') or 'No Email'}, {con_row.get('Phone','') or 'No Phone'}"
                else:
                    replaces_str = "None currently linked in Salesforce"
                
                # Format variables individually into your exact preferred comma layout
                full_name = f"{r.get(fields[0],'') or ''} {r.get(fields[1],'') or ''}".strip()
                t_val = str(r.get(fields[2], '')).strip()
                e_val = str(r.get(fields[3], '')).strip()
                p_val = str(r.get(fields[4], '')).strip()
                
                line = f"{role_label}: {full_name}, {t_val}, {e_val}, {p_val}"
                line = line.replace(', ,', ',').strip(', ') # Remove double commas if any field is empty
                
                contact_updates_str += f"\n{line}\n  replaces {replaces_str}\n"
                
    if contact_updates_str:
        blocks.append(f"Contacts Update Detail:\n{contact_updates_str}")

    # 4. Optional Comments / Notes fields
    for r in pu_records_list:
        if pd.notnull(r.get('Description')) or pd.notnull(r.get('Comments__c')):
            blocks.append(f"Comments / Notes: Included on form submission context.")
            
    return "\n**********\n".join(blocks)

# =====================================================================
# 4. PASS 2 & 3: ROUTING ENGINE (GROUP BY ACCOUNT)
# =====================================================================
print(f"⚙️ Evaluating {len(df_pus)} staged Profile Updates against business routing matrices...")
grouped_stack = df_pus.groupby('Account__c')
new_history_entries = []

for account_id, group in grouped_stack:
    account_name = df_accounts.loc[account_id, 'Name']
    
    account_history = df_history[df_history['AccountId'] == account_id]
    has_expected = account_history['Subject'].str.startswith('Profile Update expected', na=False).any()
    has_profile_up = account_history['Subject'].str.startswith('AISC Profile Update for', na=False).any()
    
    first_row = group.iloc[0]
    submitter_email = str(first_row.get('Email__c', '')).strip().lower()
    submitter_name = first_row.get('Name__c', '')
    
    matched_contact = df_contacts[df_contacts['Email'].str.lower() == submitter_email]
    contact_id = matched_contact.iloc[0].name if len(matched_contact) == 1 else None
    
    # Establish Context Variables
    target_case_id = None
    final_comments = ""
    case_subject = f"AISC Profile Update for {account_name} [{first_row['Name']}]"

    if len(group) == 1:
        pu_record = group.to_dict('records')[0]
        
        if not has_expected and not has_profile_up:
            final_comments = build_comment_blocks([pu_record], account_id)
            print(f"💼 Routing Situation 1 (New Case) for {account_name}")
            
        elif has_expected:
            target_case_row = account_history[account_history['Subject'].str.startswith('Profile Update expected')].iloc[0]
            target_case_id = target_case_row['Id']
            case_subject = f"AISC Profile Update for {account_name} [{pu_record['Name']}]"
            final_comments = build_comment_blocks([pu_record], account_id)
            print(f"🔄 Routing Situation 2 (Append to Case {target_case_row['Case.Name']})")
            
        elif has_profile_up:
            target_case_row = account_history[account_history['Subject'].str.startswith('AISC Profile Update for')].iloc[0]
            target_case_id = target_case_row['Id']
            case_subject = f"{target_case_row['Subject']} [{pu_record['Name']}]"
            final_comments = build_comment_blocks([pu_record], account_id)
            print(f"📎 Routing Situation 3 (Append to existing Profile Update Case {target_case_row['Case.Name']})")

    else:
        distinct_emails = group['Email__c'].nunique()
        if distinct_emails > 1:
            print(f"🚨 Discrepancy Flag: Multiple email submitters for {account_name}. Generating Task.")
            sf.Task.create({
                'OwnerId': PRIMARY_RESPONDER_ID,
                'Subject': f"Straighten out conflicting Profile Update submissions: {account_name}",
                'Status': 'Not Started', 'Priority': 'High'
            })
            continue
            
        group_sorted = group.sort_values('CreatedDate', ascending=False)
        pu_list_sorted = group_sorted.to_dict('records')
        
        types = group['Type__c'].fillna('').tolist()
        if 'Key Data' in types and '' in types:
            final_comments = build_comment_blocks(pu_list_sorted, account_id, multi_note="Concatenated Note: Key Data and standard layout variant consolidated below.")
        else:
            final_comments = build_comment_blocks(pu_list_sorted, account_id, multi_note="Multiple Submissions")
            
        print(f"📦 Routing Situation 4 (Consolidated Multi-Record Base) for {account_name}")

    # =====================================================================
    # 5. EXECUTE WRITE ACTIONS (CREATE VS CHATTER APPEND)
    # =====================================================================
    if target_case_id:
        sf.Case.update(target_case_id, {'Subject': case_subject})
        sf.FeedItem.create({'ParentId': target_case_id, 'Body': final_comments})
        print(f"📝 Appended data update cleanly to Case {target_case_row['Case.Name']} Chatter feed.")
    else:
        case_payload = {
            'Subject': case_subject, 'AccountId': account_id, 'ContactId': contact_id,
            'OwnerId': CERTIFICATION_QUEUE_ID, 'Primary_Responder__c': PRIMARY_RESPONDER_ID,
            'Status': 'Pending', 'Origin': 'Participant Portal',
            'Label_new__c': 'Participant Portal', 'Description': '' 
        }
        res = sf.Case.create(case_payload)
        new_case_id = res['id']
        case_num = sf.Case.get(new_case_id)['CaseNumber']
        print(f"🎉 Successfully created new case {case_num}")
        
        comment_payload = {
            'ParentId': new_case_id,
            'CommentBody': final_comments,
            'IsPublished': False 
        }
        sf.CaseComment.create(comment_payload)
        print(f"🔒 Internal Comments populated for Case {case_num}.")
        
        new_case_row = create_history_cache_row(
            case_id=new_case_id,
            case_number=case_num,
            account_id=account_id,
            contact_id=contact_id,
            case_subject=case_subject
        )
        new_history_entries.append(new_case_row)

# =====================================================================
# 6. COMMIT SYSTEM STATE EXTENSIONS TO CACHE
# =====================================================================
if new_history_entries:
    df_updated_history = pd.concat([df_history, pd.DataFrame(new_history_entries)], ignore_index=True)
    df_updated_history.to_csv(HISTORY_FILE, index=False)
    print(f"💾 Updated local tracking cache file '{HISTORY_FILE}'.")

print("\n🏁 State Engine Execution Loop finalized successfully.")