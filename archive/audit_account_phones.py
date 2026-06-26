import os
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce
from utils import clean_phone  # Importing your reference function

load_dotenv()

print("🔌 Connecting to Salesforce...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# SOQL Query matching your criteria
# Adjust 'Certification_Status__c' if your custom field name varies
query = """
    SELECT Id, Name, Cert_Certification_Status__c, BillingCountry, Phone 
    FROM Account 
    WHERE Cert_Certification_Status__c != NULL 
    AND Phone != NULL
"""

print("📡 Pulling active certified accounts with phone numbers...")
try:
    results = sf.query_all(query)
    records = results['records']
    
    if records:
        # 1. Convert to DataFrame and drop metadata
        df = pd.DataFrame(records).drop(columns='attributes', errors='ignore')
        
        # 2. Rename standard fields for your final report alignment
        df = df.rename(columns={
            'Certification_Status__c': 'Certification Status',
            'BillingCountry': 'Billing Country',
            'Phone': 'Phone Number'
        })
        
        print("⚙️ Running 'clean_phone' utility engine on data stack...")
        
        # 3. Create the 'Revised Phone Number' column by mapping your utility function
        df['Revised Phone Number'] = df['Phone Number'].apply(clean_phone)
        
        # 4. Save to CSV for your Data Loader / Human-in-the-loop review
        output_filename = 'account_phone_audit.csv'
        df.to_csv(output_filename, index=False)
        
        print(f"✅ Success! Created '{output_filename}' with {len(df)} records.")
        print("\n--- Quick Side-by-Side Preview ---")
        print(df[['Name', 'Phone Number', 'Revised Phone Number']].head(10))
        
    else:
        print("ℹ️ No accounts matched the criteria.")

except Exception as e:
    print(f"❌ An error occurred during the audit pull: {e}")
