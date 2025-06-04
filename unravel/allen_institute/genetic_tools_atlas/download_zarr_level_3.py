#!/usr/bin/env python3

"""
Download only level 3 from STPT .zarr datasets using S3 paths from a CSV file.

Usage:
    ./download_level3.py <path_to_csv>
"""

import os
import sys
import pandas as pd
import s3fs

# Load CSV
df = pd.read_csv(
    sys.argv[1],
    usecols=["MapMySectionsID", "STPT Data File Path"]
)

# Output directory
output_dir = "MMS_downloads_level3"
os.makedirs(output_dir, exist_ok=True)

# Set up S3 filesystem
fs = s3fs.S3FileSystem(anon=True)

# --- Extract experiment ID from S3 path
def extract_experiment_id(path: str) -> str:
    parts = path.strip("/").split("/")
    for part in reversed(parts):
        if part.isdigit():
            return part
    return "unknownID"

# --- Loop through all rows
for idx, row in df.iterrows():
    try:
        sections_id = row["MapMySectionsID"].replace(".", "_")
        stpt_path = row["STPT Data File Path"].rstrip("/")
        numeric_id = extract_experiment_id(stpt_path)
        id_name = f"{sections_id}_{numeric_id}"

        # Paths
        zarr_root = stpt_path
        local_root = os.path.join(output_dir, f"{id_name}.zarr")

        if not os.path.exists(local_root):
            os.makedirs(local_root)

        print(f"[{idx}] Downloading level 3 of: {zarr_root} → {local_root}")

        # Download required top-level metadata files
        for meta_file in [".zattrs", ".zgroup"]:
            s3_meta = f"{zarr_root}/{meta_file}"
            local_meta = os.path.join(local_root, meta_file)
            try:
                fs.get(s3_meta, local_meta)
            except FileNotFoundError:
                print(f"[{idx}] ⚠️ Skipped missing metadata: {meta_file}")

        # Download only resolution level 3
        s3_level3 = f"{zarr_root}/3"
        local_level3 = os.path.join(local_root, "3")
        fs.get(s3_level3, local_level3, recursive=True)

    except Exception as e:
        print(f"[{idx}] ⚠️ Error processing row: {e}")
