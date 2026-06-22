#!/usr/bin/env python3
"""
Use ``./voxel-wise_correlations.py`` from UNRAVEL to compute voxel-wise Pearson correlations between images 
(e.g., a c-Fos effect image and MERFISH  gene-expression images), restricted to voxels defined by one or more mask images.

This script was developed for use with a c-Fos effect image (-y) such as:
    delta_z = group1_cfos_z - group2_cfos_z

Usage:
------
    cfos_gene_voxel_corr_simple.py \
        -y iso_vs_awake_delta_zcfos.nii.gz \
        -g 'MERFISH_direct/*.nii.gz' 'MERFISH_imputed/*.nii.gz' \
        -m cluster3_mask.nii.gz brain_mask.nii.gz merfish_valid_mask.nii.gz \
        -o cluster3_gene_corr.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich import print
from rich.traceback import install
from pathlib import Path
from scipy.stats import pearsonr

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_nii
from unravel.core.utils import log_command, match_files, verbose_end_msg, verbose_start_msg
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument("-x", "--x_images", help="Glob pattern(s) for X-axis images (e.g., 'MERFISH_direct/*.nii.gz').", required=True, nargs='*', action=SM)
    reqs.add_argument('-y', '--y_image', help='path/y_axis_image.nii.gz (e.g., a Δz c-Fos image)', required=True, action=SM)
    reqs.add_argument("-m", "--masks", help="List of mask paths to combine for voxel inclusion (AND logic).", nargs="*", required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument("-o", "--output", help="Output CSV path. Default: voxel-wise_correlations.csv", action=SM, default="voxel-wise_correlations.csv")
    opts.add_argument("-w", "--workers", help=f"Number of gene images to process in parallel. Default: 8.", type=int, default=8, action=SM)  

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)  
    
    return parser.parse_args()


def vx_correlation(x_nii_path: Path, y_img_masked: np.ndarray, mask_img: np.ndarray, shape: tuple[int, ...]) -> dict:
    try:
        gene_img = load_nii(x_nii_path)
        if gene_img.shape[:3] != shape:
            raise ValueError(f"Shape mismatch: {gene_img.shape[:3]} != {shape}")

        x_img_masked = gene_img[mask_img]
        

        # For example, x could be a gene expression map and y could be a c-Fos effect map (e.g., Δz), both masked to the same voxels.
        r, _ = pearsonr(x_img_masked, y_img_masked) 

        return {
            "x_image": str(x_nii_path.name),
            "r": r,
            "r2": r * r if np.isfinite(r) else np.nan,
            "n_voxels": int(x_img_masked.size),
            "mean": float(np.mean(x_img_masked)),
            "percent_nonzero": float(np.mean(x_img_masked != 0) * 100.0),
            "status": "ok" if np.isfinite(r) else "zero_variance_or_nan",

        }
    except Exception as e:
        return {
            "x_image": str(x_nii_path.name),
            "r": np.nan,
            "r2": np.nan,
            "n_voxels": int(x_img_masked.size),
            "mean": np.nan,
            "percent_nonzero": np.nan,
            "status": f"error: {e}",
        }


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    y_img = load_nii(args.y_image)

    mask_paths = match_files(args.masks)
    mask_imgs = [load_mask(path) for path in mask_paths] if mask_paths else []
    mask_img = np.ones(y_img.shape, dtype=bool) if not mask_imgs else np.logical_and.reduce(mask_imgs)

    if mask_img.shape[:3] != y_img.shape[:3]:
        print(f"\n    [red1]Error: Mask shape {mask_img.shape} does not match Y image shape {y_img.shape}. Exiting...\n")
        return

    y_img_masked = y_img[mask_img]

    x_nii_paths = match_files(args.x_images)
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(vx_correlation, x_path, y_img_masked, mask_img, y_img.shape): x_path
            for x_path in x_nii_paths
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            if i == 1 or i % 100 == 0 or i == len(futures):
                print(f"Finished {i:,}/{len(futures):,}")
            results.append(fut.result())

    df = pd.DataFrame(results)
    df.insert(0, "y_image", str(Path(args.y_image).name))

    df = df.sort_values("r", ascending=False)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Saved: {out}")

    verbose_end_msg()

if __name__ == "__main__":
    main()
