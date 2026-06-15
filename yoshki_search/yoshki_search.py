import csv
import re
import requests
import time

# File configurations
INPUT_FILE = 'mapped_urls.csv'
OUTPUT_RESULTS = 'yoshki_results_multi.csv'
OUTPUT_ERRORS = 'scraping_errors_secondPass.csv'

# Your target code snippet or ID
CODE_TO_FIND = '55879r'  # 55170r for Single and 55879r for Multi

def check_for_code(url, snippet, max_bytes=50000):
    """Streams content chunk-by-chunk. Returns ('STATUS', 'Error Message or None')."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    # Re-prepend https:// just in case since mapped_urls.csv is stripped
    if not url.startswith(('http://', 'https://')):
        full_url = 'https://' + url
    else:
        full_url = url

    try:
        with requests.get(full_url, headers=headers, timeout=(3.05, 10), stream=True) as response:
            if response.status_code != 200:
                return "ERROR", f"HTTP Status Code {response.status_code}"
                
            bytes_received = 0
            downloaded_text = ""
            
            for chunk in response.iter_content(chunk_size=2048, decode_unicode=True):
                if chunk:
                    # If the chunk is raw bytes, convert it to text safely
                    if isinstance(chunk, bytes):
                        chunk_text = chunk.decode('utf-8', errors='ignore')
                    else:
                        chunk_text = chunk

                    downloaded_text += chunk_text
                    bytes_received += len(chunk_text.encode('utf-8'))
                    
                    # Quick Check 1: Did we find our code snippet yet?
                    if snippet in downloaded_text:
                        return "FOUND", None
                    # Quick Check 2: Safety limit for endless loops
                    if bytes_received > max_bytes:
                        break
            
            if snippet in downloaded_text:
                return "FOUND", None
            else:
                return "NOT FOUND", None
                
    except requests.exceptions.Timeout:
        return "ERROR", "Connection Timed Out"
    except requests.exceptions.SSLError:
        return "ERROR", "SSL/TLS Certificate Verification Failed"
    except requests.exceptions.ConnectionError:
        return "ERROR", "Failed to Connect (Dead Domain or DNS Error)"
    except requests.exceptions.RequestException as e:
        return "ERROR", f"Unhandled Exception: {type(e).__name__}"

def main():
    success_results = []
    error_results = []

    print(f"Reading mapped accounts from {INPUT_FILE}...")
    
    try:
        with open(INPUT_FILE, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            for row in reader:
                account_id = row.get('id')
                stripped_url = row.get('stripped_url')
                
                if not stripped_url:
                    continue
                
                print(f"Scanning Account {account_id} ({stripped_url})...", end="", flush=True)
                
                # Run the stream-safe check
                status, error_msg = check_for_code(stripped_url, CODE_TO_FIND)
                
                if status == "ERROR":
                    print(f" ❌ [ERROR: {error_msg}]")
                    error_results.append({
                        'id': account_id,
                        'url': stripped_url,
                        'error_reason': error_msg
                    })
                else:
                    print(f" [{status}]")
                    success_results.append({
                        'id': account_id,
                        'url': stripped_url,
                        'status': status
                    })
                
                # Polite pause between requests
                time.sleep(0.5)

    except FileNotFoundError:
        print(f"Error: Could not find '{INPUT_FILE}'.")
        return

    # 1. Save successful scans (Found / Not Found)
    print(f"\n💾 Saving scan results to {OUTPUT_RESULTS}...")
    with open(OUTPUT_RESULTS, mode='w', encoding='utf-8', newline='') as out_res:
        writer = csv.DictWriter(out_res, fieldnames=['id', 'url', 'status'])
        writer.writeheader()
        writer.writerows(success_results)

    # 2. Save categorized errors to their own file
    print(f"💾 Saving error log to {OUTPUT_ERRORS}...")
    with open(OUTPUT_ERRORS, mode='w', encoding='utf-8', newline='') as out_err:
        writer = csv.DictWriter(out_err, fieldnames=['id', 'url', 'error_reason'])
        writer.writeheader()
        writer.writerows(error_results)

    print("\nAll tasks finished!")
    print(f"-> Clean Results Saved: {len(success_results)}")
    print(f"-> Errors Logged: {len(error_results)}")

if __name__ == "__main__":
    main()