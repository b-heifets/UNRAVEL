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
    reqs.add_argument('-x', '--x_img_glob', help='path/x_axis_image_*.nii.gz (gene expression maps; first word in filename = gene).', required=True, action=SM)
    reqs.add_argument('-y', '--y_img_glob', help='path/y_axis_image_*.nii.gz (e.g., cFos maps).', required=True, action=SM)
    reqs.add_argument('-a', '--atlas', help='path/atlas.nii.gz.', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/output.csv.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', default=None, action=SM)
    opts.add_argument('-yn', '--y_name', help='Name for the Y-axis image column. Default: cFos', default='cFos', action=SM)

    return parser.parse_args()


def calculate_mean_intensities_parallel(y_img_path, x_img_path, atlas_img, region_ids):
    """Extracts region-wise mean intensities for an X image."""
    try:
        group, mouse_id = Path(y_img_path).stem.split('_')[:2]
        gene = Path(x_img_path).stem.split('_')[0]
        img = load_nii(x_img_path)
        region_mean_dict = calculate_mean_intensity(atlas_img, img, regions=region_ids)
        return group, mouse_id, gene, region_mean_dict
    except Exception as e:
        print(f"[red]    Error processing {x_img_path}: {e}")
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
    x_img_paths = [Path(file) for file in sorted(glob(args.x_img_glob))]
    y_img_paths = [Path(file) for file in sorted(glob(args.y_img_glob))]
    if not x_img_paths or not y_img_paths:
        print("\n    [red]No X or Y images found. Exiting...\n")
        return

    print(f"\n    Processing {len(x_img_paths)} X images and {len(y_img_paths)} Y images...")
    all_results = []
    with Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), "[progress.percentage]{task.percentage:>3.0f}%") as progress:
        task = progress.add_task("Processing images...", total=len(x_img_paths) * len(y_img_paths))

        # Process each Y image
        for y_img_path in y_img_paths:
            print(f"\n    Loading Y-axis image and masking: [bold cyan]{y_img_path}\n")
            
            imgY = np.where(mask_img, load_nii(y_img_path), 0)
            imgY_region_mean_dict = calculate_mean_intensity(atlas_img, imgY, regions=region_ids)

            futures = []
            with ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(calculate_mean_intensities_parallel, y_img_path, x_img_path, atlas_img, region_ids)
                    for x_img_path in x_img_paths
                ]

                for future in as_completed(futures):
                    result = future.result()
                    if result is not None:
                        group, mouse_id, gene, region_mean_dict = result
                        for region, mean in region_mean_dict.items():
                            all_results.append({
                                'Group': group,
                                'MouseID': mouse_id,
                                'RegionID': region,
                                'Gene': gene,
                                'Mean': mean
                            })
                    progress.advance(task)

    # Create a dataframe from results
    results_df = pd.DataFrame(all_results)

    # Pivot table to have genes as columns
    results_pivot_df = results_df.pivot_table(
        index=['Group', 'MouseID', 'RegionID'], 
        columns='Gene', 
        values='Mean'
    ).reset_index()

    # Add the Y-axis intensities (e.g., cFos) to the final DataFrame
    y_data = pd.DataFrame.from_dict(imgY_region_mean_dict, orient='index', columns=[args.y_name])
    y_data.index.name = 'RegionID'
    y_data.reset_index(inplace=True)
    final_df = pd.merge(results_pivot_df, y_data, on='RegionID', how='left')

    # Move the Y-axis column to after the RegionID column
    cols = final_df.columns.tolist()
    cols = cols[:3] + [cols[-1]] + cols[3:-1]
    final_df = final_df[cols]

    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output_path, index=False)

if __name__ == '__main__':
    main()
