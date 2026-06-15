import csv
import re

# --- CONFIGURATION ---
INPUT_FILE = 'maybe_urls.csv'

# Output File Names
OUTPUT_1_CLEAN_UNIQUE = 'url_list.csv'
OUTPUT_2_CLEAN_MAPPED = 'mapped_urls.csv'
OUTPUT_3_BAD_RECORDS   = 'bad_urls.csv'

# Note for the bad records file
TODAYS_NOTE = 'Bad URL removed 6/2/26'

# Safe, linear, case-insensitive RegEx pattern
URL_PATTERN = re.compile(r'^(https?://)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(/[^\s]*)?$', re.IGNORECASE)

def clean_and_strip_protocol(raw_url):
    """Checks if valid. If so, returns (clean_url_with_https, domain_only_without_http)."""
    if not raw_url:
        return None, None
    raw_url = raw_url.strip()
    if URL_PATTERN.match(raw_url):
        if not raw_url.startswith(('http://', 'https://')):
            full_url = 'https://' + raw_url
        else:
            full_url = raw_url
        
        stripped_url = re.sub(r'^https?://', '', full_url, flags=re.IGNORECASE)
        return full_url, stripped_url
    return None, None

def main():
    unique_clean_urls = set()
    mapped_records = []        
    bad_records = []           

    print(f" Reading {INPUT_FILE}...")
    
    try:
        with open(INPUT_FILE, mode='r', encoding='utf-8') as infile:
            # Read rows as standard lists first to fix header casing issues
            reader = csv.reader(infile)
            headers = [h.strip().lower() for h in next(reader)] # Force headers to lowercase
            
            # Find the index of the ID and URL columns safely
            id_idx = None
            url_idx = None
            
            for i, h in enumerate(headers):
                if 'id' in h:  # Will match 'id', 'account id', 'account_id', 'Id'
                    id_idx = i
                if 'url' in h or 'site' in h or 'web' in h: # Matches 'url', 'website', etc.
                    url_idx = i
            
            # Fallback defaults if it can't find them
            if id_idx is None: id_idx = 0
            if url_idx is None: url_idx = 1
            
            # Process the rows
            for row in reader:
                if not row:
                    continue
                
                # Extract fields safely using our discovered positions
                account_id = row[id_idx].strip() if id_idx < len(row) else ''
                raw_url = row[url_idx].strip() if url_idx < len(row) else ''
                
                if not account_id and not raw_url:
                    continue
                
                full_url, stripped_url = clean_and_strip_protocol(raw_url)
                
                if full_url:
                    unique_clean_urls.add(full_url)
                    mapped_records.append({
                        'id': account_id,
                        'stripped_url': stripped_url
                    })
                else:
                    bad_records.append({
                        'id': account_id,
                        'url': raw_url,
                        'Blank': '',
                        'Note': TODAYS_NOTE
                    })
                    
    except FileNotFoundError:
        print(f"Error: Could not find '{INPUT_FILE}'.")
        return

    # 1. Save Unique Clean List
    print(f"💾 Saving unique scraping list to: {OUTPUT_1_CLEAN_UNIQUE}")
    with open(OUTPUT_1_CLEAN_UNIQUE, mode='w', encoding='utf-8', newline='') as out1:
        writer = csv.writer(out1)
        writer.writerow(['url'])
        for url in sorted(unique_clean_urls):
            writer.writerow([url])

    # 2. Save Mapped List
    print(f"💾 Saving mapped account URLs to: {OUTPUT_2_CLEAN_MAPPED}")
    with open(OUTPUT_2_CLEAN_MAPPED, mode='w', encoding='utf-8', newline='') as out2:
        writer = csv.DictWriter(out2, fieldnames=['id', 'stripped_url'])
        writer.writeheader()
        writer.writerows(mapped_records)

    # 3. Save Bad Records List
    print(f"💾 Saving bad records log to: {OUTPUT_3_BAD_RECORDS}")
    with open(OUTPUT_3_BAD_RECORDS, mode='w', encoding='utf-8', newline='') as out3:
        writer = csv.DictWriter(out3, fieldnames=['id', 'url', 'Blank', 'Note'])
        writer.writeheader()
        writer.writerows(bad_records)

    print("\nProcessing complete!")
    print(f"-> Total Unique Valid URLs: {len(unique_clean_urls)}")
    print(f"-> Total Mapped Accounts: {len(mapped_records)}")
    print(f"-> Total Bad Records Flags: {len(bad_records)}")

if __name__ == "__main__":
    main()
