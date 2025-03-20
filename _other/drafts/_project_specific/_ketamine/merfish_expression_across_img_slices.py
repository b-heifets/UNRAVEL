#!/usr/bin/env python3

"""
Calculate the mean expression of a MERFISH expression map across slices of the brain.

Prereqs:
    - merfish_expression_to_nii.py
    - or CCF30_to_MERFISH.py

Notes:
    - Lower numbers for brain sections indicate more posterior sections.

Usage:
------
    ./merfish_expression_across_img_slices.py -i path/input.csv [-mas path/mask1.nii.gz path/mask2.nii.gz ...] [-o path/output.csv]
"""

import nibabel as nib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.cluster_stats.validation import cluster_bbox
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_nii
from unravel.core.utils import log_command
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/input.csv', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', default=None, action=SM)
    opts.add_argument('-o', '--output', help='Output path for the saved .csv file. Default: <input>.csv', default=None, action=SM)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    # Load the expression map
    img = load_nii(args.input)

    print("\n    Loading masks and making composite mask...")
    mask_imgs = [load_mask(path) for path in args.masks] if args.masks else []
    mask_img = np.ones(img.shape, dtype=bool) if not mask_imgs else np.logical_and.reduce(mask_imgs)

    # Get the bounding box of the region
    _, xmin, xmax, ymin, ymax, zmin, zmax = cluster_bbox(1, mask_img)  # zmin and zmax are the posterior and anterior limits

    # Apply the mask to the expression map
    img *= mask_img

    # Calculate the mean expression in non-zero voxels across the region for each slice from zmax to zmin
    print("\n    Calculating slice-wise mean expression within masked region...")
    slice_means = []
    # Calculate the mean expression in masked voxels across each slice
    for z in range(zmax, zmin - 1, -1):
        slice_data = img[:, :, z]
        slice_mask = mask_img[:, :, z]
        masked_voxels = slice_data[slice_mask]
        mean_val = masked_voxels.mean() if masked_voxels.size > 0 else np.nan
        slice_means.append((z, mean_val))
        print(f"    Slice == {z}; mean in mask == {mean_val:.2f}")

    # Optionally save results to a CSV
    output_csv = args.output if args.output else Path(args.input).with_suffix('').as_posix() + "_slice_means.csv"
    df = pd.DataFrame(slice_means, columns=['z_index', 'mean_expression'])
    df.to_csv(output_csv, index=False)
    print(f"\n    Saved slice-wise mean expression values to {output_csv}\n")
    

if __name__ == '__main__':
    main()
