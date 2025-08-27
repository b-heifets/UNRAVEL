#!/usr/bin/env python3

"""
Use ``_other/drafts/correlation.py`` from UNRAVEL to calculate the region-wise correlation between two images.

Inputs:
    - The X-axis images may be gene expression maps. The first word in the filename is used as the gene name in the output.

Outputs:
    - CSV files saved in a directory named 'regional_gene_correlations'.
    - Columns: Gene, Correlation

Note:
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020_regional_summary.csv
    - It has columns: Region_ID, ID_Path, Region, Abbr, General_Region, R, G, B
    - Alternatively, use CCFv3-2017_regional_summary.csv or provide a custom CSV with the same columns.
    
Usage:
------
    _other/drafts/correlation_parallel.py -x path/x_axis_image_<asterisk>.nii.gz -y path/y_axis_image1.nii.gz -a path/atlas.nii.gz [-mas path/mask1.nii.gz] [-csv CCFv3-2020_regional_summary.csv] [-v]
"""

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from rich import print
from rich.progress import Progress, BarColumn, TextColumn
from rich.traceback import install
from scipy.stats import pearsonr

from _other.drafts._tabular_data.key_value_to_excel import key_val_to_excel
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files
from unravel.core.img_io import load_nii
from unravel.region_stats.rstats_mean_IF import calculate_mean_intensity
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-x', '--x_input', help="Glob pattern(s) for X-axis images (e.g., 'path/x_axis_image_*.nii.gz').", required=True, nargs='*', action=SM)
    reqs.add_argument('-y', '--y_input', help="Glob pattern(s) for Y-axis images (e.g., 'path/y_axis_image_*.nii.gz').", required=True, nargs='*', action=SM)
    reqs.add_argument('-a', '--atlas', help='Path to the atlas NIfTI file for a region-wise correlation.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', default=None, action=SM)
    opts.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020_regional_summary.csv', default='CCFv3-2020_regional_summary.csv', action=SM)

    return parser.parse_args()

def run_correlation_safe(x_img_path, imgY, atlas_img, mask_img):
    """
    Wrapper for running the correlation computation for a specific X and Y file pair.
    Captures results for sequential printing.
    """
    try:
        imgX = load_nii(x_img_path)
        imgX = np.where(mask_img, imgX, 0) # Apply mask to X image

        gene = str(Path(x_img_path).name).split('_')[0]
        correlation = compute_regionwise_correlation_parallel(imgX, imgY, atlas_img)[0]

        result = (gene, correlation)
        return result

    except Exception as e:
        return f"Error for: {Path(x_img_path).name} {str(e)}\n"

def compute_regionwise_correlation_parallel(imgX, imgY, atlas_img):
    """Compute the region-wise correlation between two images, using the provided atlas image and mask image."""

    # Get unique region IDs from the atlas image
    unique_regions = np.unique(atlas_img)

    # Calculate the mean intensity of the images in each region
    imgX_mean_intensities_dict = calculate_mean_intensity(atlas_img, imgX, regions=unique_regions)
    imgY_mean_intensities_dict = calculate_mean_intensity(atlas_img, imgY, regions=unique_regions)

    # Convert the dictionaries to DataFrames
    imgX_df = pd.DataFrame(imgX_mean_intensities_dict.items(), columns=['Region', 'ImgX_Mean'])
    imgY_df = pd.DataFrame(imgY_mean_intensities_dict.items(), columns=['Region', 'ImgY_Mean'])

    # Merge the DataFrames on the region column
    merged_df = pd.merge(imgX_df, imgY_df, on='Region')

    # Compute the Pearson correlation between the mean intensities
    correlation = pearsonr(merged_df['ImgX_Mean'], merged_df['ImgY_Mean'])

    return correlation


@log_command
def main():
    install()
    args = parse_args()

    print("\n    Loading masks and making composite mask...")
    mask_imgs = [load_mask(path) for path in args.masks] if args.masks else []
    mask_img = np.ones(atlas_img.shape, dtype=bool) if not mask_imgs else np.logical_and.reduce(mask_imgs)

    print("\n    Loading atlas image and applying mask...")
    atlas_img = load_nii(args.atlas)
    atlas_img = np.where(mask_img, atlas_img, 0)

    x_img_paths = match_files(args.x_input)
    y_img_paths = match_files(args.y_input)
    if len(x_img_paths) == 0 or len(y_img_paths) == 0:
        print("\n    [red1]No X or Y images found. Exiting...\n")
        return

    # Use Rich progress bar
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
    ) as progress:
        # Iterate over Y-axis images
        for y_img_path in y_img_paths:
            print(f"\n    Loading Y-axis image and masking: [bold cyan]{y_img_path}")

            imgY = load_nii(y_img_path)
            imgY = np.where(mask_img, imgY, 0)

            # Add progress task for X-axis images
            task_id = progress.add_task(f"Processing {y_img_path.name}", total=len(x_img_paths))
            
            # Get correlation results for each X image in parallel
            print(f"\n    Calculating region-wise correlations for {len(x_img_paths)} X-axis images...\n")
            results = []
            with ThreadPoolExecutor() as executor:
                tasks = [
                    (x_img_path, imgY, atlas_img, mask_img)
                    for x_img_path in x_img_paths
                ]

                future_to_task = {executor.submit(run_correlation_safe, *task): task for task in tasks}

                for future in as_completed(future_to_task):
                    result = future.result()
                    if result:
                        results.append(result)
                    progress.advance(task_id)

            # Separate valid results and errors
            valid_results = []
            errors = []
            for res in results:
                if isinstance(res, tuple) and len(res) == 2:
                    valid_results.append(res)
                else:
                    errors.append(res)

            # Handle empty results
            if not valid_results:
                print(f"No valid results for {y_img_path}. Skipping...")
                continue

            # Log errors if any
            if errors:
                error_log_path = "correlation_errors.log"
                with open(error_log_path, "w") as f:
                    for err in errors:
                        f.write(f"{err}\n")
                print(f"Logged errors to {error_log_path}")

            # Create DataFrame for valid results
            results_df = pd.DataFrame(valid_results, columns=['Gene', 'Correlation'])

            # Save to CSV
            output_name = str(Path(y_img_path).name).replace('.nii.gz', '_regional_gene_correlations.csv')
            output_path = Path('regional_gene_correlations') / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            results_df.to_csv(output_path, index=False)
            
            
if __name__ == '__main__':
    main()