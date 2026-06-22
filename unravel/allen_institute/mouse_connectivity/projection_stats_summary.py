#!/usr/bin/env python3
"""
Use ``projection_stats_summary.py`` from UNRAVEL to compute/summarize basic statistics on projection density NIfTI files.

Prereqs:
    - ``download_and_convert_CCF_aligned_images.py``

Note:
    - https://community.brain-map.org/t/api-allen-brain-connectivity/2988
    - projection density = sum of detected pixels / count of all pixels in the region
    - The projection density image in CCF space is not binary due to linear interpolation during the warping process.
    - projection energy = sum of detected pixel intensity / count of all pixels in the region

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
    opts.add_argument('-o', '--output', help='Output CSV file path. Default: projection_stats_summary.csv', default=None, action=SM)
    opts.add_argument('-t', '--threshold', help='Intensity threshold to consider a voxel as "detected" in the projection density map. Default: 0.15', default=0.15, type=float, action=SM)
    opts.add_argument('-c', '--criteria', help='Criteria to filter regions (e.g., "< 20000" for right hemisphere regions only with a split atlas). Default: None', default=None, action=SM)
    opts.add_argument('-ch', '--channel', help='Color channel to compute stats for (red, green, blue). Default: green', default='green', choices=['red', 'green', 'blue'], action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help="Increase verbosity. Default: False", action="store_true", default=False)
    return parser.parse_args()


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
        print(f"Computing projection stats for region IDs: {sorted(region_ids)}")

    dir_paths = match_files(args.input) if args.input else [Path().cwd()]

    # Initialize df with columns: experiment_id, region_id, region_vx_n, projection_sum, projection_density, projection_thresh, projection_intensity, projection_energy

    df = pd.DataFrame(columns=["experiment_id", "region_id", "region_vx_n", "projection_sum", "projection_density", "projection_thresh", "projection_intensity", "projection_energy"])

    for dir_path in dir_paths:

        id = dir_path.name.split('_')[0]

        projection_path = dir_path / f"{id}_projection_density_25um.nii.gz"
        projection_img = load_nii(projection_path)
        img_path = dir_path / f"{id}_resampled_{args.channel}.nii.gz"
        img = load_nii(img_path)

        for region_id in region_ids:
            region_mask = atlas_img == int(region_id)

            print(f"Processing region ID {region_id}...")

            # Extract voxel values for the region and confirm voxel count
            region_img_vals = img[region_mask]            
            region_voxel_count = region_img_vals.size
            if region_voxel_count == 0:
                print(f"[yellow]Warning: No voxels found for region ID {region_id} in atlas.[/yellow]")
                continue

            # projection density = sum of detected pixels / count of all pixels in the region
            region_proj_vals = projection_img[region_mask]  # Projection intensities within the region (0-1 range)
            if np.sum(region_proj_vals) == 0:
                print(f"[yellow]Warning: No projection detected for region ID {region_id} in file {projection_path.name}.[/yellow]")
                continue
            sum_val = np.sum(region_proj_vals)
            projection_density = sum_val / region_voxel_count

            # projection energy = sum of detected pixel intensity / count of all pixels in the region
            projection_energy = np.sum(region_img_vals[region_proj_vals >= args.threshold]) / region_voxel_count

            # projection intensity = mean of detected pixel intensity within the segmented voxels
            projection_intensity = np.mean(region_img_vals[region_proj_vals > args.threshold])

            # Append to df
            df = pd.concat([df, pd.DataFrame({
                "experiment_id": [int(id)],
                "region_id": [int(region_id)],
                "region_vx_n": [region_voxel_count],
                "projection_sum": [sum_val],
                "projection_density": [projection_density],
                "projection_thresh": [args.threshold],
                "projection_intensity": [projection_intensity],
                "projection_energy": [projection_energy]
            })], ignore_index=True)

    # Sort by projection_density descending
    df = df.sort_values(by='projection_density', ascending=False).reset_index(drop=True)

    # Print final DataFrame
    pd.set_option('display.float_format', '{:.6f}'.format)
    print(f"\nProjection Stats Summary:\n{df}\n")

    # Save df to CSV
    output_csv_path = args.output if args.output else "projection_stats_summary.csv"
    df.to_csv(output_csv_path, index=False)
    if args.verbose:
        print(f"Saved projection stats summary to {output_csv_path}")

    verbose_end_msg()


if __name__ == "__main__":
    main()
