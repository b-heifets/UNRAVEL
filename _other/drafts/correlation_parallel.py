#!/usr/bin/env python3

"""
Use ``_other/drafts/correlation.py`` from UNRAVEL to calculate the region-wise correlation between two images.

Inputs:
    - The X-axis images may be gene expression maps. The first word in the filename is used as the gene name in the output.

Outputs:
    - A CSV file for each Y-axis image with columns: Gene, Pearson correlation, p-value

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
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.stats import pearsonr

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command
from unravel.core.img_io import load_nii
from unravel.region_stats.rstats_mean_IF import calculate_mean_intensity
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-x', '--x_img_glob', help='path/x_axis_image_*.nii.gz', required=True, action=SM)
    reqs.add_argument('-y', '--y_image', help='path/y_axis_image.nii.gz (can pass in list of images)', nargs='*', required=True, action=SM)
    reqs.add_argument('-a', '--atlas', help='Path to the atlas NIfTI file for a region-wise correlation. Default: None', required=True, action=SM)

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

        correlation, p_value = compute_regionwise_correlation_parallel(imgX, imgY, atlas_img)

        gene = str(Path(x_img_path).name).split('_')[0]

        # Format the result
        result = (
            f"Gene,{gene}\n"
            f"Pearson correlation,{correlation}\n"
            f"p-value,{p_value}"
        )

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
    correlation, p_value = pearsonr(merged_df['ImgX_Mean'], merged_df['ImgY_Mean'])

    return correlation, p_value


@log_command
def main():
    install()
    args = parse_args()

    y_img_paths = [Path(y_image) for y_image in args.y_image]
    x_img_paths = [Path(file) for file in glob(args.x_img_glob)]
    mask_imgs = [load_mask(path) for path in args.masks] if args.masks else []
    mask_img = np.ones(atlas_img.shape, dtype=bool) if not mask_imgs else np.logical_and.reduce(mask_imgs)

    if Path(args.atlas).exists():
        atlas_img = load_nii(args.atlas)
    else:
        print(f"\n    [red1]{Path(args.atlas).exists()} does not exist. Exiting...\n")
        return

    for y_img_path in y_img_paths:
        print("\n")
        print(f"[bold cyan]{y_img_path}[/bold cyan]")
        print("\n")

        if y_img_path.exists():
            imgY = load_nii(y_img_path)
        else:
            print(f"    [red1]{y_img_path} does not exist. Skipping...")
            continue

        # Apply mask(s) if provided
        imgY_masked = np.where(mask_img, imgY, 0)
        atlas_img_masked = np.where(mask_img, atlas_img, 0)

        # Get correlation results for each X image in parallel
        results = []
        with ThreadPoolExecutor() as executor:
            tasks = [
                (x_img_path, imgY_masked, atlas_img_masked, mask_img)
                for x_img_path in x_img_paths
            ]
            future_to_task = {executor.submit(run_correlation_safe, *task): task for task in tasks}

            for future in as_completed(future_to_task):
                result = future.result()
                results.append(result)

        for result in results:
            print(result)

        # Save the results to a CSV file
        output_path = str(y_img_path).replace('.nii.gz', '_correlations.csv')
        with open(output_path, 'w') as f:
            f.write('\n'.join(results))


if __name__ == '__main__':
    main()