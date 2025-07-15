#!/usr/bin/env python3

"""
segmentation_summary.py

Compute voxel counts and proportions for somata (1), endothelial cells (3),
and astrocytes (4) from Ilastik .nii.gz outputs and save to CSV summaries.

By default, if you don’t pass -o/--output, each sample will get its own
CSV in its MMS_seg folder named <sample>_segmentation_summary.csv.
You can still override with -o to write a single combined CSV.
"""

import os
import argparse
import nibabel as nib
import numpy as np

def get_seg_voxel_counts(seg_folder, classes):
    counts = {}
    for label, name in classes.items():
        fname = f"MMS_seg_{label}.nii.gz"
        fp = os.path.join(seg_folder, fname)
        if not os.path.isfile(fp):
            counts[name] = 0
            continue
        img = nib.load(fp)
        data = img.get_fdata()
        counts[name] = int(np.count_nonzero(data))
    return counts

def compute_proportions(counts):
    total = sum(counts.values())
    if total == 0:
        return {name: 0.0 for name in counts}
    return {name: counts[name] / total for name in counts}

def process_and_write_line(sample, seg_folder, fout, classes):
    counts = get_seg_voxel_counts(seg_folder, classes)
    total = sum(counts.values())
    props = compute_proportions(counts)
    fout.write(
        f"{sample},"
        f"{counts['somata']},{counts['endothelial']},{counts['astrocytes']},"
        f"{total},"
        f"{props['somata']:.4f},{props['endothelial']:.4f},{props['astrocytes']:.4f}\n"
    )

def _walk_and_write(root, fout, classes):
    # sample dir?
    if os.path.isdir(os.path.join(root, "MMS_seg")):
        sample = os.path.basename(os.path.normpath(root))
        seg_folder = os.path.join(root, "MMS_seg")
        process_and_write_line(sample, seg_folder, fout, classes)
    else:
        for sample in sorted(os.listdir(root)):
            sam_path = os.path.join(root, sample)
            seg_folder = os.path.join(sam_path, "MMS_seg")
            if not os.path.isdir(seg_folder):
                continue
            process_and_write_line(sample, seg_folder, fout, classes)

def main(root_dirs, output_csv):
    classes = {1: 'somata', 3: 'endothelial', 4: 'astrocytes'}
    header = (
        "sample,"
        "somata_count,endothelial_count,astrocytes_count,"
        "total_count,"
        "somata_prop,endothelial_prop,astrocytes_prop\n"
    )

    if output_csv:
        if os.path.exists(output_csv):
            print(f"Combined output '{output_csv}' already exists; skipping.")
            return
        with open(output_csv, 'w') as fout:
            fout.write(header)
            for root in root_dirs:
                _walk_and_write(root, fout, classes)
    else:
        for root in root_dirs:
            # individual sample directory?
            if os.path.isdir(os.path.join(root, "MMS_seg")):
                sample = os.path.basename(os.path.normpath(root))
                seg_folder = os.path.join(root, "MMS_seg")
                out_fp = os.path.join(seg_folder, f"{sample}_segmentation_summary.csv")
                if os.path.exists(out_fp):
                    print(f"Skipping {sample}: '{out_fp}' already exists.")
                    continue
                with open(out_fp, 'w') as fout:
                    fout.write(header)
                    process_and_write_line(sample, seg_folder, fout, classes)
            else:
                # parent directory containing multiple samples
                for sample in sorted(os.listdir(root)):
                    sam_path = os.path.join(root, sample)
                    seg_folder = os.path.join(sam_path, "MMS_seg")
                    if not os.path.isdir(seg_folder):
                        continue
                    out_fp = os.path.join(seg_folder, f"{sample}_segmentation_summary.csv")
                    if os.path.exists(out_fp):
                        print(f"Skipping {sample}: '{out_fp}' already exists.")
                        continue
                    with open(out_fp, 'w') as fout:
                        fout.write(header)
                        process_and_write_line(sample, seg_folder, fout, classes)

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Summarize Ilastik segmentations across samples."
    )
    p.add_argument(
        "root_dirs",
        nargs="+",
        help="One or more parent directories or individual sample dirs."
    )
    p.add_argument(
        "-o", "--output",
        help=(
            "Path for a combined summary CSV. "
            "If omitted, each sample gets its own CSV in its MMS_seg folder."
        )
    )

    args = p.parse_args()
    main(args.root_dirs, args.output)

