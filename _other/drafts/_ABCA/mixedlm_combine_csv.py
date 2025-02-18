#!/usr/bin/env python3

"""
Use ``mixedlm_csv.py`` from UNRAVEL to generate a CSV for smf.mixedlm() analysis, containing region-wise intensities for X and Y images.

Inputs:
    - Y-axis images: e.g., cFos maps (first word = group, second word = mouse ID).

Output:
    - CSV with columns: Group, MouseID, RegionID, cFos, Gene1, Gene2, ...
    
Usage:
------
    mixedlm_csv.py -x path/x_axis_image_<asterisk>.nii.gz -y path/y_axis_image_<asterisk>.nii.gz -a path/atlas.nii.gz -o output.csv [-mas path/mask1.nii.gz]
"""

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from glob import glob
from pathlib import Path
from rich import print
from rich.progress import Progress, BarColumn, TextColumn
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command
from unravel.core.img_io import load_nii
from unravel.region_stats.rstats_mean_IF import calculate_mean_intensity
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-x', '--x_vars_csv', help='path/merfish.csv.', required=True, action=SM)
    reqs.add_argument('-y', '--y_var_csv', help='path/lsfm.csv.', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/output.csv.', required=True, action=SM)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    # Load the LSFM and MERFISH CSVs
    merfish_df = pd.read_csv(args.x_vars_csv)
    lsfm_df = pd.read_csv(args.y_var_csv)

    # Merge on RegionID
    combined_df = lsfm_df.merge(merfish_df, on="RegionID", how="left")

    # Sort by Group and MouseID
    combined_df.sort_values(["Group", "MouseID"], inplace=True)

    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(output_path, index=False)

if __name__ == '__main__':
    main()
