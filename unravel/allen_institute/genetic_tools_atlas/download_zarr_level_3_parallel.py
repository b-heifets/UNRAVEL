#!/usr/bin/env python3

"""
Download only level 3 from STPT .zarr datasets using S3 paths from a CSV file, in parallel.

Usage:
    ./download_level3_parallel.py <path_to_csv>
"""

import os
import sys
import pandas as pd
import s3fs
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup output directory and S3
output_dir = "MMS_downloads_level3"
os.makedirs(output_dir, exist_ok=True)
fs = s3fs.S3FileSystem(anon=True)

# --- Extract experiment ID
def extract_experiment_id(path: str) -> str:
    parts = path.strip("/").split("/")
    for part in reversed(parts):
        if part.isdigit():
            return part
    return "unknownID"

# --- Download a single row
def download_level3(row, idx):
    try:
        sections_id = row["MapMySectionsID"].replace(".", "_")
        stpt_path = row["STPT Data File Path"].rstrip("/")
        numeric_id = extract_experiment_id(stpt_path)
        id_name = f"{sections_id}_{numeric_id}"

        zarr_root = stpt_path
        local_root = os.path.join(output_dir, f"{id_name}.zarr")

        if os.path.exists(os.path.join(local_root, "3")):
            return f"[{idx}] Skipping {id_name} (already exists)"

        os.makedirs(local_root, exist_ok=True)
        print(f"[{idx}] Downloading: {id_name}")

        # Metadata
        for meta_file in [".zattrs", ".zgroup"]:
            s3_meta = f"{zarr_root}/{meta_file}"
            local_meta = os.path.join(local_root, meta_file)
            try:
                fs.get(s3_meta, local_meta)
            except FileNotFoundError:
                print(f"[{idx}] ⚠️ Missing metadata: {meta_file}")

        # Level 3
        s3_level3 = f"{zarr_root}/3"
        local_level3 = os.path.join(local_root, "3")
        fs.get(s3_level3, local_level3, recursive=True)

        return f"[{idx}] ✅ Done: {id_name}"

    except Exception as e:
        return f"[{idx}] ❌ Error: {e}"

# --- Main
def main():
    csv_path = sys.argv[1]
    df = pd.read_csv(csv_path, usecols=["MapMySectionsID", "STPT Data File Path"])
    print(f"Loaded {len(df)} rows. Starting parallel downloads...\n")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_level3, row, idx) for idx, row in df.iterrows()]
        for f in as_completed(futures):
            print(f.result())

if __name__ == "__main__":
    main()
