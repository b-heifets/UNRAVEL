#!/usr/bin/env python3
"""
soma_in_grey.py

For a directory of “*_seg_1.nii.gz” segmentation volumes, computes—for each file—
the count of nonzero voxels falling in each atlas label, divides by the total voxels
of that label in the atlas, and writes per‐sample CSVs into a “somata_grey/” folder.

Usage:
    python soma_in_grey.py /path/to/combined_dir \
        -a /path/to/atlas_CCFv3_2020_30um.nii.gz

This will look for:
/path/to/combined_dir/*_seg_1.nii.gz
and output:
/path/to/combined_dir/somata_grey/<sample>_somata_in_grey.csv
"""

import os
import glob
import argparse

import nibabel as nib
import numpy as np
import pandas as pd

try:
    from nibabel.processing import resample_from_to
except ImportError:
    resample_from_to = None


def process_seg(seg_path, atlas_img, labels, threshold, out_dir, force):
    # sample name = filename without "_seg_1.nii.gz"
    fname = os.path.basename(seg_path)
    if not fname.endswith("_seg_1.nii.gz"):
        return
    sample = fname[:-len("_seg_1.nii.gz")]

    out_csv = os.path.join(out_dir, f"{sample}_somata_in_grey.csv")
    if os.path.exists(out_csv) and not force:
        print(f"Skipping {sample}: '{out_csv}' exists. (Use --force)")
        return

    if resample_from_to is None:
        raise RuntimeError("nibabel.processing.resample_from_to required; please upgrade nibabel")

    # load segmentation
    seg_img = nib.load(seg_path)
    seg_data = seg_img.get_fdata()

    # resample atlas into seg grid if needed
    atlas_res = atlas_img
    if atlas_img.shape != seg_img.shape:
        atlas_res = resample_from_to(atlas_img, seg_img, order=0)
    atlas_data = atlas_res.get_fdata()

    # mask and check
    mask = seg_data > threshold
    if mask.sum() == 0:
        print(f"[WARN] No voxels >{threshold} in {fname}")
        return

    records = []
    for lbl in labels:
        cnt = int(np.logical_and(mask, atlas_data == lbl).sum())
        total_label = int((atlas_data == lbl).sum())
        if total_label == 0:
            prop = 0.0
            print(f"[WARN] Label {lbl} missing in atlas for {sample}")
        else:
            prop = cnt / total_label
        records.append({"label": lbl, "count": cnt, "proportion": prop})

    df = pd.DataFrame(records, columns=["label", "count", "proportion"])
    df.to_csv(out_csv, index=False)
    print(f"[OK] {sample}: wrote {out_csv}")


def main():
    p = argparse.ArgumentParser(
        description="Compute soma‐in‐grey proportions for *_seg_1.nii.gz files."
    )
    p.add_argument("seg_dir",
                   help="Directory containing *_seg_1.nii.gz files")
    p.add_argument("-a", "--atlas", required=True,
                   help="Path to atlas_CCFv3_2020_30um.nii.gz")
    p.add_argument("-l", "--labels", nargs="+", type=int, default=[890],
                   help="Atlas labels to include (default: 890)")
    p.add_argument("-t", "--threshold", type=float, default=0,
                   help="Segmentation threshold (voxels > t; default=0)")
    p.add_argument("-o", "--output_dir", default=None,
                   help="Override output directory (otherwise uses seg_dir/somata_grey)")
    p.add_argument("-f", "--force", action="store_true",
                   help="Overwrite existing CSVs")

    args = p.parse_args()

    # load the common atlas one time
    atlas_img = nib.load(args.atlas)

    # determine output directory
    out_dir = args.output_dir or os.path.join(args.seg_dir, "somata_grey")
    os.makedirs(out_dir, exist_ok=True)

    # find all *_seg_1.nii.gz files
    pattern = os.path.join(args.seg_dir, "*_seg_1.nii.gz")
    seg_files = sorted(glob.glob(pattern))
    if not seg_files:
        print(f"No files matching '*_seg_1.nii.gz' in {args.seg_dir}")
        return

    # process each segmentation
    for seg_path in seg_files:
        process_seg(seg_path, atlas_img, args.labels,
                    args.threshold, out_dir, args.force)


if __name__ == "__main__":
    main()

