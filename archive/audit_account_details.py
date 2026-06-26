import os
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import clean_phone, fix_capitalization  # Import our shared logic engine

load_dotenv()

print("🔌 Connecting to Salesforce...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# Updated SOQL Query: Kept the certification filter, removed the phone null restriction; excluding STEELFAB
query = """
    SELECT Id, Name, Cert_Certification_Status__c, BillingCountry, Phone 
    FROM Account 
    WHERE Cert_Certification_Status__c != NULL
    AND Cert_Certification_Status__c != 'Dropped'
    AND Id != '0015w00002E4sGMAAZ'
    AND (NOT Name LIKE 'Ω%')
    AND (NOT Name LIKE 'Ψ%')
    AND (NOT Name LIKE '%[P]')
    AND (NOT Name LIKE '%[p]')
"""

print("📡 Fetching active certified accounts matrix...")
try:
    results = sf.query_all(query)
    records = results['records']
    
    if records:
        # 1. Convert to DataFrame and drop Salesforce system metadata
        df = pd.DataFrame(records).drop(columns='attributes', errors='ignore')
        
        # 2. Rename columns to match your preferred data dictionary naming convention
        df = df.rename(columns={
            'Name': 'Account Name',
            'Cert_Certification_Status__c': 'Certification Status',
            'BillingCountry': 'Billing Country',
            'Phone': 'Phone Number'
        })
        
        # Fill NaN values in Phone Number column with empty strings so string functions don't crash
        df['Phone Number'] = df['Phone Number'].fillna('')
        
        print("⚙️ Evaluating data against text capitalization and phone formatting algorithms...")
        
        # 3. Generate your revised suggestions using your utils library
        df['Revised Account Name'] = df['Account Name'].apply(fix_capitalization)
        df['Revised Phone Number'] = df['Phone Number'].apply(clean_phone)
        
        # 4. EXCEPTION FILTER ENGINE
        # Keep only the rows where the original name doesn't match the suggestion
        # OR where the original phone number doesn't match the suggestion
        name_changed_mask = df['Account Name'] != df['Revised Account Name']
        phone_changed_mask = df['Phone Number'] != df['Revised Phone Number']
        
        df_exceptions = df[name_changed_mask | phone_changed_mask].copy()
        
        # 5. Output management
        output_filename = 'account_detail_audit.csv'
        df_exceptions.to_csv(output_filename, index=False)
        
        print(f"✅ Success! Generated '{output_filename}'.")
        print(f"📊 Total Records Evaluated: {len(df)}")
        print(f"🚨 Exception Rows Requiring Updates: {len(df_exceptions)}")
        
        if not df_exceptions.empty:
            print("\n--- Exception Preview ---")
            print(df_exceptions[['Account Name', 'Revised Account Name', 'Phone Number', 'Revised Phone Number']].head(10))
        
    else:
        print("ℹ️ No accounts matched the execution parameters.")

except Exception as e:
    print(f"❌ An error occurred during the details audit execution: {e}")