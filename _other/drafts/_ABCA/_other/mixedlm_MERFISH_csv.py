#!/usr/bin/env python3

"""
Use ``mixedlm_csv.py`` from UNRAVEL to generate a CSV for smf.mixedlm() analysis, containing region-wise intensities for X and Y images.

Inputs:
    - X-axis images: gene expression maps (first word in filename = gene).
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
from pathlib import Path
from rich import print
from rich.progress import Progress, BarColumn, TextColumn
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files
from unravel.core.img_io import load_nii
from unravel.region_stats.rstats_mean_IF import calculate_mean_intensity
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-x', '--x_input', help='path/x_axis_image_*.nii.gz (gene expression maps; first word in filename = gene).', required=True, nargs='*', action=SM)
    reqs.add_argument('-a', '--atlas', help='path/atlas.nii.gz.', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/output.csv.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', default=None, action=SM)

    return parser.parse_args()


def calculate_mean_intensities_parallel_merfish(merfish_img_path, atlas_img, region_ids):
    """Extracts region-wise mean intensities for an X image."""
    try:
        gene = Path(merfish_img_path).stem.split('_')[0]
        img = load_nii(merfish_img_path)
        region_mean_dict = calculate_mean_intensity(atlas_img, img, regions=region_ids)
        return gene, region_mean_dict
    except Exception as e:
        print(f"[red]    Error processing {merfish_img_path}: {e}")
        return None


@log_command
def main():
    install()
    args = parse_args()

    # Load atlas and masks
    print("\n    Loading atlas and masks...")
    atlas_img = load_nii(args.atlas)
    mask_img = np.logical_and.reduce([load_mask(m) for m in args.masks]) if args.masks else np.ones_like(atlas_img, dtype=bool)
    atlas_img = np.where(mask_img, atlas_img, 0)
    region_ids = np.unique(atlas_img[atlas_img > 0])

    # Collect image paths
    merfish_img_paths = match_files(args.x_input)
    if not merfish_img_paths:
        print("\n    [red]No MERFISH images found. Exiting...\n")
        return

    print(f"\n    Processing {len(merfish_img_paths)} MERFISH images...")
    all_results = []
    with Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), "[progress.percentage]{task.percentage:>3.0f}%") as progress:
        task = progress.add_task("Processing images...", total=len(merfish_img_paths))
        futures = []
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(calculate_mean_intensities_parallel_merfish, merfish_img_path, atlas_img, region_ids)
                for merfish_img_path in merfish_img_paths
            ]

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    gene, region_mean_dict = result
                    for region, mean in region_mean_dict.items():
                        all_results.append({
                            'RegionID': region,
                            'Gene': gene,
                            'Mean': mean
                        })
                progress.advance(task)

    # Create a dataframe from results
    results_df = pd.DataFrame(all_results)

    # Pivot table to have genes as columns
    results_pivot_df = results_df.pivot_table(
        index=['RegionID'], 
        columns='Gene', 
        values='Mean'
    ).reset_index()

    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_pivot_df.to_csv(output_path, index=False)

if __name__ == '__main__':
    main()
