#!/usr/bin/env python3
"""
Use ``injection_stats_summary.py`` from UNRAVEL to compute/summarize basic statistics on injection density NIfTI files.

Prereqs:
    - ``download_and_convert_CCF_aligned_injection_density.py``

Note:
    - The injection density represents the % of a region's volume that corresponds to the injection site.
    - https://community.brain-map.org/t/api-allen-brain-connectivity/2988
    - injection density = sum of segmented pixels / sum of all pixels in division or mask
    - The injection density image in CCF space is not binary, but values range from 0-1 due to linear interpolation during the warping process.

Usage:
------
    `injection_stats_summary.py -i 113144533 [-a atlas_CCFv3_2020_25um.nii.gz] [-o output.csv] [-v]`
"""

import numpy as np
from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.img_io import load_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-a', '--atlas', help='Path to atlas .nii.gz (e.g., atlas_CCFv3_2020_25um_split.nii.gz) or a mask .nii.gz file.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Input dir(s) to process or pattern(s). Default: current working directory", default=None, nargs="*", action=SM)
    opts.add_argument('-r', '--region_ids', help='Region IDs to compute stats for. Default: all regions in atlas.', default=None, type=int, nargs="*", action=SM)
    opts.add_argument('-o', '--output', help='Output CSV file path. Default: injection_stats_summary.csv', default=None, action=SM)
    opts.add_argument('-c', '--criteria', help='Criteria to filter regions (e.g., "< 20000" for right hemisphere regions only with a split atlas). Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help="Increase verbosity. Default: False", action="store_true", default=False)
    return parser.parse_args()

# TODO: Could add a measure of specificity: injection density in region / injection density in whole brain
# TODO: Could report the % of the injection that falls within a given region. sum of injection density in region / # of voxels in injection site

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    atlas_img = load_nii(args.atlas)

    region_ids = set(args.region_ids) if args.region_ids else set(np.unique(atlas_img))
    region_ids.discard(0)  # Skip background region ID 0

    if args.criteria:
        filtered_region_ids = set()
        for region_id in region_ids:
            try:
                if eval(f"{int(region_id)} {args.criteria}"):
                    filtered_region_ids.add(region_id)
            except Exception as e:
                print(f"[red]Error evaluating criteria '{args.criteria}' for region ID {region_id}: {e}[/red]")
        region_ids = filtered_region_ids

    if args.verbose:
        print(f"Computing injection stats for region IDs: {sorted(region_ids)}")

    dir_paths = match_files(args.input) if args.input else [Path().cwd()]

    # Initialize df with columns: experiment_id, region_id, region_vx_n, injection_sum, injection_density
    df = pd.DataFrame(columns=["experiment_id", "region_id", "region_vx_n", "injection_sum", "injection_density"])

    for dir_path in dir_paths:

        id = dir_path.name.split('_')[0]

        injection_path = dir_path / f"{id}_injection_density_25um.nii.gz"
        injection_img = load_nii(injection_path)

        for region_id in region_ids:
            region_mask = atlas_img == int(region_id)

            print(f"Processing region ID {region_id}...")

            # Extract voxel values for the region and confirm voxel count
            region_img_vals = atlas_img[region_mask]          
            region_voxel_count = region_img_vals.size
            if region_voxel_count == 0:
                print(f"[yellow]Warning: No voxels found for region ID {region_id} in atlas.[/yellow]")
                continue

            # injection density = sum of detected pixels / sum of all pixels in division
            region_injection_vals = injection_img[region_mask]  # Injection intensities within the region (0-1 range)
            if np.sum(region_injection_vals) == 0:
                print(f"[yellow]Warning: No injection detected for region ID {region_id} of {Path(args.atlas).name} in file {injection_path.name}.[/yellow]")
                continue
            sum_val = np.sum(region_injection_vals)
            injection_density = sum_val / region_voxel_count

            # Append to df
            df = pd.concat([df, pd.DataFrame({
                "experiment_id": [int(id)],
                "region_id": [int(region_id)],
                "region_vx_n": [region_voxel_count],
                "injection_sum": [sum_val],
                "injection_density": [injection_density],
            })], ignore_index=True)

    # Sort by injection_density descending
    df = df.sort_values(by='injection_density', ascending=False).reset_index(drop=True)
    # Print final DataFrame
    pd.set_option('display.float_format', '{:.6f}'.format)
    print(f"\nInjection Stats Summary:\n{df}\n")

    # Save df to CSV
    output_csv_path = args.output if args.output else "injection_stats_summary.csv"
    df.to_csv(output_csv_path, index=False)
    if args.verbose:
        print(f"Saved injection stats summary to {output_csv_path}")

    verbose_end_msg()


if __name__ == "__main__":
    main()
