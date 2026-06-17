import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.secrets")
API_KEY = os.getenv("SF_OPENDATA_API_KEY")

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = (SCRIPT_DIR / "../data/raw").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Socrata resource IDs mapped to filenames
# We use the resources you provided
DATASETS = {
    "parcels.csv": "acdm-wktn",
    "land_use_current.csv": "c5ge-t6pj", # Base Land Use dataset (Public)
    "zoning_districts.csv": "xzez-p3nc"
}

def download_dataset(filename, resource_id):
    filepath = DATA_DIR / filename
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if API_KEY:
        headers['X-App-Token'] = API_KEY

    # Check remote count
    print(f"Checking remote row count for {filename}...")
    try:
        count_url = f"https://data.sfgov.org/resource/{resource_id}.json?$select=count(*)"
        attempt = 0
        while True:
            count_resp = requests.get(count_url, headers=headers)
            if count_resp.status_code == 200:
                break
            attempt += 1
            print(f"  [Count Attempt {attempt}] Received {count_resp.status_code}. Retrying in 2s...")
            time.sleep(2)
        count_resp.raise_for_status()
        remote_count = int(count_resp.json()[0]['count'])
    except Exception as e:
        print(f"Could not get remote count: {e}. Will force download.")
        remote_count = -1

    if filepath.exists():
        print(f"Checking local row count for {filename}...")
        # Count local lines
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            local_lines = sum(1 for _ in f)
        local_count = local_lines - 1 if local_lines > 0 else 0
        
        if remote_count != -1 and local_count >= remote_count:
            print(f"File {filename} already exists and has all {local_count} rows (API reports {remote_count}). Skipping download.")
            return
        else:
            print(f"File {filename} exists but has {local_count} rows (API reports {remote_count}). Redownloading...")
    else:
        print(f"File {filename} not found locally. Preparing to download {remote_count} rows...")

    print(f"Downloading {filename} from DataSF with pagination...")
    start_time = time.time()

    limit = 50000
    offset = 0
    first_chunk = True

    with open(filepath, 'wb') as f:
        while True:
            # We use the /resource/ endpoint which supports SoQL limits and offsets natively
            url = f"https://data.sfgov.org/resource/{resource_id}.csv?$limit={limit}&$offset={offset}"
            print(f"  Fetching offset {offset}...")
            
            attempt = 0
            while True:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    break
                attempt += 1
                print(f"  [Chunk Attempt {attempt}] Received {response.status_code}. Retrying in 2s...")
                time.sleep(2)
            response.raise_for_status()
            
            # The response is text (CSV format)
            # Split into lines to easily strip the header from chunks 2+
            lines = response.content.splitlines(keepends=True)
            
            if len(lines) <= 1:
                # Only header or completely empty
                if first_chunk:
                    f.writelines(lines)
                break
                
            if first_chunk:
                f.writelines(lines)
                first_chunk = False
            else:
                # Skip the header line for subsequent chunks
                f.writelines(lines[1:])
            
            # If we received fewer rows than the limit (plus 1 for header), we are at the end
            if len(lines) - 1 < limit:
                break
                
            offset += limit
            
            # Be respectful to the API
            time.sleep(1.0)
            
    elapsed = time.time() - start_time
    print(f"Finished downloading {filename} in {elapsed:.2f} seconds.")

def main():
    print("Starting SF OpenData Pull...")
    for filename, resource_id in [list(DATASETS.items())[0]]:
        download_dataset(filename, resource_id)
    print("Data pull complete.")

if __name__ == "__main__":
    # Ensure script runs from its directory or parent correctly
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    main()
