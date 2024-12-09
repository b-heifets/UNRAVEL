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
    opts.add_argument('-yn', '--y_name', help='Name of the Y-axis image (e.g., cFos). Default: cFos', default='cFos', action=SM)

    return parser.parse_args()

def extract_regional_intensities(x_img_path, imgY, atlas_img, mask_img, y_name='cFos'):
    """Extract region-wise mean intensities for X and Y images."""
    try:
        imgX = load_nii(x_img_path)
        imgX = np.where(mask_img, imgX, 0)

        # Extract region means
        region_ids = np.unique(atlas_img)
        imgX_means = calculate_mean_intensity(atlas_img, imgX, regions=region_ids)
        imgY_means = calculate_mean_intensity(atlas_img, imgY, regions=region_ids)

        # Create dataframe
        gene = Path(x_img_path).stem.split('_')[0]
        df = pd.DataFrame({'RegionID': list(imgX_means.keys()), y_name: list(imgY_means.values()), gene: list(imgX_means.values())})
        return df
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

    # Collect image paths
    x_img_paths = [Path(file) for file in sorted(glob(args.x_img_glob))]
    y_img_paths = [Path(file) for file in sorted(glob(args.y_img_glob))]
    if not x_img_paths or not y_img_paths:
        print("\n    [red]No X or Y images found. Exiting...\n")
        return

    print(f"\n    Processing {len(x_img_paths)} X images and {len(y_img_paths)} Y images...")
    all_results = []
    failed_tasks = []

    with Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), "[progress.percentage]{task.percentage:>3.0f}%") as progress:
        task = progress.add_task("Processing images...", total=len(x_img_paths) * len(y_img_paths))

        # Process each Y image
        for y_img_path in y_img_paths:
            try:
                print(f"\n    Loading Y-axis image and masking: [bold cyan]{y_img_path}\n")

                imgY = np.where(mask_img, load_nii(y_img_path), 0)
                group, mouse_id = Path(y_img_path).stem.split('_')[:2]

                futures = []
                with ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(extract_regional_intensities, x_img_path, imgY, atlas_img, mask_img, args.y_name)
                        for x_img_path in x_img_paths
                    ]

                    for future in as_completed(futures):
                        result = future.result()
                        if result is not None:
                            result['Group'] = group
                            result['MouseID'] = mouse_id
                            all_results.append(result)
                        else:
                            failed_tasks.append(f"Failed: {x_img_path} for {y_img_path}")
                        progress.advance(task)

            except IndexError:
                print(f"[yellow]Warning: Filename format does not match expected 'Group_MouseID'. Skipping: {y_img_path}")
                failed_tasks.append(f"Skipped due to filename: {y_img_path}")
    # Combine results
    print("\n    Combining results...")
    combined_df = pd.concat(all_results, axis=0, ignore_index=True)
    cols = combined_df.columns.tolist()
    cols = cols[:4] + sorted(cols[4:])
    combined_df = combined_df[cols]

    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(output_path, index=False)

    # Log failed tasks
    if failed_tasks:
        print(f"\n    [yellow]Warning: {len(failed_tasks)} tasks failed or were skipped:")
        for task in failed_tasks:
            print(f"    {task}")
    else:
        print("\n    [green]All tasks completed successfully!\n")


if __name__ == '__main__':
    main()
