import os
import pandas as pd
from dotenv import load_dotenv
from simple_salesforce import Salesforce

# Load credentials from your root .env file
load_dotenv()

print("🔌 Connecting to Salesforce...")
sf = Salesforce(
    username=os.getenv('SF_USERNAME'),
    password=os.getenv('SF_PASSWORD'),
    security_token=os.getenv('SF_TOKEN')
)

# Define the SOQL query using Salesforce's built-in date literal 'LAST_N_DAYS:30'
# Standard Case object fields: Note that Case Number is 'CaseNumber' (not 'Name')
query = """
    SELECT Id, CaseNumber, ContactId, AccountId, Status, Subject, CreatedDate, LastModifiedDate 
    FROM Case 
    WHERE (Subject LIKE 'AISC Profile Update for%' OR Subject LIKE 'Profile Update expected for%')
    AND CreatedDate = LAST_N_DAYS:30
"""

print("📡 Pulling profile update cases from the last 30 days...")
try:
    results = sf.query_all(query)
    records = results['records']
    
    if records:
        # Convert to DataFrame and drop the Salesforce metadata column
        df = pd.DataFrame(records).drop(columns='attributes', errors='ignore')
        
        # Rename CaseNumber to Case.Name to match your tracking preference
        df = df.rename(columns={'CaseNumber': 'Case.Name'})
        
        # Save to CSV (local execution directory)
        output_filename = 'pu_cases_1mhistory.csv'
        df.to_csv(output_filename, index=False)
        
        print(f"✅ Success! Created '{output_filename}' with {len(df)} records.")
        print("\n--- Quick Preview ---")
        print(df[['Case.Name', 'Status', 'Subject']].head())
    else:
        print("ℹ️ No cases matched those subject prefixes in the last 30 days.")

except Exception as e:
    print(f"❌ An error occurred during the pull: {e}")