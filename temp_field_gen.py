import os
from simple_salesforce import Salesforce
from dotenv import load_dotenv

load_dotenv()
sf = Salesforce(username=os.getenv('SF_USERNAME'), password=os.getenv('SF_PASSWORD'), security_token=os.getenv('SF_TOKEN'))

# Ask Salesforce to describe the object and list all real API names
desc = sf.Company_Profile_Change__c.describe()
fields = [f['name'] for f in desc['fields']]

print("📋 REAL API FIELDS FOUND ON OBJECT:")
for field in sorted(fields):
    if "Quality" in field or "Title" in field:
        print(f" ✨ {field}")
        