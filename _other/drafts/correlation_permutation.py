#!/usr/bin/env python3

"""
Use ``_other/drafts/correlation_permutation.py`` from UNRAVEL to calculate the region-wise correlation between two images and check for significance using permutation testing.

Inputs:
    - The X-axis images may be MERFISH gene expression maps in the form of 3D images. 
    - The first word in the filename is used as the gene name in the output.

Outputs:
    - A CSV file for each Y-axis image with columns: Gene, Pearson correlation, p-value

Note:
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020_regional_summary.csv
    - It has columns: Region_ID, ID_Path, Region, Abbr, General_Region, R, G, B
    - Alternatively, use CCFv3-2017_regional_summary.csv or provide a custom CSV with the same columns.
    
Usage:
------
    _other/drafts/correlation_permutation.py -x path/x_axis_image_<asterisk>.nii.gz -y path/y_axis_image1.nii.gz -a path/atlas.nii.gz [-mas path/mask1.nii.gz] [-csv CCFv3-2020_regional_summary.csv] [-v]
"""

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.stats import pearsonr

from _other.drafts._tabular_data.key_value_to_excel import key_val_to_excel
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import initialize_progress_bar, log_command
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
    opts.add_argument('-p', '--permutations', help='Number of permutations to perform. Default: 10000', default=10000, type=int, action=SM)
    opts.add_argument('-s', '--seed', help='Seed for the random number generator used for permutations. Default: 42', default=42, type=int, action=SM)

    return parser.parse_args()
    

def run_correlation_safe(x_img_path, imgY, atlas_img, mask_img, n_permutations=10000, seed=42):
    """
    Wrapper for running the correlation computation for a specific X and Y file pair.
    Captures results for sequential printing.
    """
    try:
        imgX = load_nii(x_img_path)
        imgX = np.where(mask_img, imgX, 0) # Apply mask to X image

        correlation, p_value = parallel_regionwise_correlations_and_permutations(imgX, imgY, atlas_img, n_permutations, seed)

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

def parallel_regionwise_correlations_and_permutations(imgX, imgY, atlas_img, n_permutations=10000, seed=42):
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

    # Convert each series to a numpy array
    imgX_mean = merged_df['ImgX_Mean'].to_numpy().squeeze()
    imgY_mean = merged_df['ImgY_Mean'].to_numpy().squeeze()

    # Compute the Pearson correlation between the mean intensities
    observed_corr = pearsonr(imgX_mean, imgY_mean)[0]

    # Vectorized permutation testing with a fixed seed
    rng = np.default_rng(seed=seed) 
    permuted_corrs = np.array([
        pearsonr(rng.permutation(imgX_mean), imgY_mean)[0]
        for _ in range(n_permutations)
    ])

    # Calculate p-value (Test if the observed_corr is greater than what is expected by chance, regardless of the direction)
    permuted_corrs = np.array(permuted_corrs)
    p_value = np.mean(np.abs(permuted_corrs) >= np.abs(observed_corr))

    return observed_corr, p_value


@log_command
def main():
    install()
    args = parse_args()

    y_img_paths = [Path(y_image) for y_image in args.y_image]
    x_img_paths = [Path(file) for file in glob(args.x_img_glob)]

    # Load masks if provided
    mask_imgs = []
    if args.masks:
        for mask_path in args.masks:
            mask_imgs.append(load_mask(mask_path))

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
        if mask_imgs:
            mask_img = np.ones(imgY.shape, dtype=bool)
            for mask in mask_imgs:
                mask_img = mask_img & mask.astype(bool)
        imgY_masked = np.where(mask_img, imgY, 0)
        atlas_img_masked = np.where(mask_img, atlas_img, 0)

        # Get correlation results for each X image in parallel
        results = []
        with ThreadPoolExecutor() as executor:
            tasks = [
                (x_img_path, imgY_masked, atlas_img_masked, mask_img, args.permutations, args.seed)
                for x_img_path in x_img_paths
            ]

            future_to_task = {executor.submit(run_correlation_safe, *task): task for task in tasks}

            progress, task_id = initialize_progress_bar(len(x_img_paths), "[red]Processing X images...")

            with Live(progress):
                for future in as_completed(future_to_task):
                    result = future.result()
                    results.append(result)
                    progress.update(task_id, advance=1)

        for result in results:
            print(result)

        # Save the results to a CSV file
        output_path = str(y_img_path).replace('.nii.gz', '_correlations_permutations.xlsx')
        key_val_to_excel(results, output_path, args.delimiter)


if __name__ == '__main__':
    main()