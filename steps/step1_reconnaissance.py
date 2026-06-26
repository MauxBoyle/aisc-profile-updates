# steps/step1_reconnaissance.py
import pandas as pd

def execute_reconnaissance(sf, account_id, pending_pus, df_history, schema_map):
    """
    Executes deep environmental evaluation for a single processing account target.
    Returns the live Salesforce Account record and a structured copy-paste roster snapshot.
    """
    print("\n🔍 [STEP 1] INITIAL ACCOUNT ENVIRONMENT RECONNAISSANCE")
    
    # -----------------------------------------------------------------
    # 1. MULTIPLICITY CHECK
    # -----------------------------------------------------------------
    # Scan the current active runtime loop array for duplicate submissions
    matching_pus = [pu['Name'] for pu in pending_pus if pu.get('Account__c') == account_id]
    pu_count = len(matching_pus)
    
    if pu_count > 1:
        print(f"   ⚠️  MULTIPLICITY ALERT: Found {pu_count} active submissions queued for this Account!")
        print(f"      Queued Record Tokens: {', '.join(matching_pus)}")
    else:
        print("   🟢 Single isolated transaction token confirmed for this account window.")
        
    # -----------------------------------------------------------------
    # 2. HISTORICAL RECORD RETROSPECTIVE
    # -----------------------------------------------------------------
    # Look back through your local log file for existing parent case links
    past_cases = df_history[df_history['AccountId'] == account_id]
    if not past_cases.empty:
        latest_case_num = past_cases.iloc[-1]['Case.Name']
        latest_case_subject = past_cases.iloc[-1]['Subject']
        print(f"   📜 HISTORICAL LOOKBACK: Linked to active history tracking thread Case {latest_case_num} ({latest_case_subject})")
    else:
        print("   ℹ️ No matching historical workspace links found in local tracking cache.")
        
    # -----------------------------------------------------------------
    # 3. DEEP LIVE ROSTER SNAPSHOT GENERATION
    # -----------------------------------------------------------------
    print("   📡 Pulling fresh live contact profile structures from Salesforce...")
    
    # Map out our sensible python keys to retrieve the correct lookup fields from the account
    role_fields = {
        'Cert Contact': schema_map.get(('Account', 'cert_contact_id'), 'Cert_Certification_Contact__c'),
        'Principal'   : schema_map.get(('Account', 'principal_contact_id'), 'Cert_Principal_Contact__c'),
        'Accounting'  : schema_map.get(('Account', 'accounting_contact_id'), 'Cert_Accounting_Contact__c'),
        'Quality'     : schema_map.get(('Account', 'quality_contact_id'), 'Cert_Marketing_Contact__c')
    }
    
    # Query the live Account record using the fields defined in your CSV dictionary
    account_query = f"SELECT Id, Name, {', '.join(role_fields.values())} FROM Account WHERE Id = '{account_id}'"
    account_record = sf.query(account_query)['records'][0]
    
    snapshot_lines = []
    snapshot_lines.append("📸 PRISTINE LIVE ROSTER PROFILE SNAPSHOT:")
    
    # Step through each role, fetch the occupant's ID, and look up their details
    for role_label, api_field in role_fields.items():
        contact_id = account_record.get(api_field)
        
        if contact_id:
            try:
                # Query the contact's deep metadata using your standardized schema requirements
                c_email = schema_map.get(('Contact', 'email_address'), 'Email')
                c_title = schema_map.get(('Contact', 'title'), 'Title')
                c_phone = schema_map.get(('Contact', 'phone'), 'Phone')
                
                con_data = sf.Contact.get(contact_id)
                
                name = con_data.get('Name', '[Name Undefined]')
                email = con_data.get(c_email, '[No Email]')
                title = con_data.get(c_title, '[No Title]')
                phone = con_data.get(c_phone, '[No Phone]')
                
                snapshot_lines.append(f"   👉 {role_label.ljust(12)}: {name} | {title} | {email} | {phone}")
            except Exception:
                snapshot_lines.append(f"   👉 {role_label.ljust(12)}: [ID Assigned: {contact_id} but record inaccessible]")
        else:
            snapshot_lines.append(f"   👉 {role_label.ljust(12)}: [Vacant Lookup Slot]")
            
    # Compile and display the complete roster grid on your screen
    snapshot_string = "\n".join(snapshot_lines)
    print(f"\n{snapshot_string}\n")
    
    return account_record, snapshot_string