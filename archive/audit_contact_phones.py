import os
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import clean_phone  # Leveraging your exact, extension-safe phone utility

load_dotenv()

print("🔌 Connecting to Salesforce...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# SOQL Relationship Query: Pulls active contacts while bypassing Dropped and Ω accounts
query = """
    SELECT Id, FirstName, LastName, Account.Name, Phone, MobilePhone 
    FROM Contact 
    WHERE AccountId != NULL 
    AND Account.Cert_Certification_Status__c != 'Dropped'
    AND (NOT Account.Name LIKE 'Ω%')
    AND (Phone != NULL OR MobilePhone != NULL)
"""

print("📡 Fetching active contact communication matrix...")
try:
    results = sf.query_all(query)
    records = results['records']
    
    if records:
        # 1. Unpack the relationship query results safely
        flat_records = []
        for r in records:
            flat_records.append({
                'Contact ID': r['Id'],
                'First Name': r.get('FirstName') or '',
                'Last Name': r.get('LastName') or '',
                'Account Name': r['Account']['Name'] if r.get('Account') else '',
                'Phone': r.get('Phone') or '',
                'Mobile Phone': r.get('MobilePhone') or ''
            })
            
        # 2. Convert to DataFrame
        df = pd.DataFrame(flat_records)
        
        print("⚙️ Running 'clean_phone' engine on contact phone numbers...")
        
        # 3. Generate your revised suggestions using your shared utils library
        df['Revised Phone'] = df['Phone'].apply(clean_phone)
        df['Revised Mobile Phone'] = df['Mobile Phone'].apply(clean_phone)
        
        # 4. EXCEPTION FILTER ENGINE
        # Keep rows ONLY if the original phone doesn't match the clean suggestion
        # OR if the original mobile phone doesn't match the clean mobile suggestion
        phone_changed = df['Phone'] != df['Revised Phone']
        mobile_changed = df['Mobile Phone'] != df['Revised Mobile Phone']
        
        df_exceptions = df[phone_changed | mobile_changed].copy()
        
        # 5. Save the Exception Report to CSV
        output_filename = 'contact_phone_audit.csv'
        df_exceptions.to_csv(output_filename, index=False)
        
        print(f"✅ Success! Generated '{output_filename}'.")
        print(f"📊 Total Active Contacts Evaluated: {len(df)}")
        print(f"🚨 Contact Exception Rows Requiring Updates: {len(df_exceptions)}")
        
        if not df_exceptions.empty:
            print("\n--- Contact Exception Preview ---")
            print(df_exceptions[['First Name', 'Last Name', 'Phone', 'Revised Phone', 'Mobile Phone', 'Revised Mobile Phone']].head(10))
            
    else:
        print("ℹ️ No contacts matched the execution parameters.")

except Exception as e:
    print(f"❌ An error occurred during the contact phone audit: {e}")