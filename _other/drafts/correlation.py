#!/usr/bin/env python3

"""
Use ``_other/drafts/correlation.py`` from UNRAVEL to calculate the region-wise or voxel-wise correlation between MERFISH-CCF gene expression and a 3D stats map.

Note:
    - If an atlas is provided, the script will calculate the region-wise correlation.
    - If no atlas is provided, the script will calculate the voxel-wise correlation.
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020_regional_summary.csv
    - It has columns: Region_ID, ID_Path, Region, Abbr, General_Region, R, G, B
    - Alternatively, use CCFv3-2017_regional_summary.csv or provide a custom CSV with the same columns.
    
Usage:
------
    _other/drafts/correlation.py -i path/to/stats_map.nii.gz -e path/to/gene_expression.nii.gz [-mas path/to/mask1.nii.gz path/to/mask2.nii.gz] [-a path/to/atlas.nii.gz] [-r 1 2 3] [-csv path/to/CCFv3-2020_regional_summary.csv] [-v]
"""

import numpy as np
import nibabel as nib
from scipy.stats import pearsonr

import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install


from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.core.img_io import load_nii
from unravel.region_stats.rstats_mean_IF import calculate_mean_intensity
from unravel.voxel_stats.apply_mask import load_mask, apply_mask_to_ndarray


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to a 3D stats map (.nii.gz)"', required=True, action=SM)
    reqs.add_argument('-e', '--exp_map', help='Path to the gene expression NIfTI (.nii.gz) file', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', default=None, action=SM)
    opts.add_argument('-a', '--atlas', help='Path to the atlas NIfTI file for a region-wise correlation. Default: None', default=None, action=SM)
    opts.add_argument('-rw', '--regional', help='Region-wise correlation. Default: False', action='store_true', default=False)
    opts.add_argument('-r', '--regions', help='Space-separated list of region IDs to process. Default: process all IDs', nargs='*', type=int, default=None, action=SM)
    opts.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020_regional_summary.csv', default='/Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/unravel/core/csvs/CCFv3-2020_regional_summary.csv', action=SM)
    opts.add_argument('-p', '--plot', help='Plot correlation. Default: False', action='store_true', default=False)
    opts.add_argument('-y', '--y_label', help='Y-axis label for the correlation plot. Default: "Statistical Map"', default='Statistical Map', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Change /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/unravel/core/csvs/CCFv3-2020_regional_summary.csv to CCFv3-2020_regional_summary.csv after testing


def compute_regionwise_correlation(exp_img, stats_img, atlas_img, mask_list=None, regions=None):
    """Compute region-wise correlation between gene expression and a 3D stats map, restricted by masks."""
    # Apply mask(s) if provided
    valid_voxels = np.ones(exp_img.shape, dtype=bool)
    if mask_list:
        for mask_data in mask_list:
            valid_voxels = valid_voxels & mask_data.astype(bool)

    # Mask the images to keep only valid voxels
    exp_img_masked = np.where(valid_voxels, exp_img, 0)
    stats_img_masked = np.where(valid_voxels, stats_img, 0)

    # Calculate the mean expression and stats values for each region (region: mean_intensity)
    mean_intensities_dict_exp = calculate_mean_intensity(atlas_img, exp_img_masked, regions=regions)
    mean_intensities_dict_p = calculate_mean_intensity(atlas_img, stats_img_masked, regions=regions)

    # Convert the dictionaries to DataFrames
    df_exp_img = pd.DataFrame(mean_intensities_dict_exp.items(), columns=['Region', 'Mean_Expression'])
    df_stats_img = pd.DataFrame(mean_intensities_dict_p.items(), columns=['Region', 'Mean_Stat'])

    # Merge the DataFrames on the region column
    merged_df = pd.merge(df_exp_img, df_stats_img, on='Region')

    # Remove regions with zero mean expression
    merged_df = merged_df[merged_df['Mean_Expression'] > 0]

    # Compute the Pearson correlation between the mean expression and stats values
    correlation, p_value = pearsonr(merged_df['Mean_Expression'], merged_df['Mean_Stat'])

    # Number of voxels used for correlation
    n_of_voxels = merged_df.shape[0]

    return correlation, p_value, merged_df, n_of_voxels

def compute_voxelwise_correlation(exp_img, img, mask_list=None):
    """Compute voxel-wise correlation between gene expression and a 3D map, restricted by masks."""

    # Check that the images have the same shape
    if exp_img.shape != img.shape:
        raise ValueError("\n    [red1]The two images must have the same shape\n")

    # Apply mask(s) if provided
    valid_voxels = np.ones(exp_img.shape, dtype=bool)
    if mask_list:
        for mask_data in mask_list:
            valid_voxels = valid_voxels & mask_data.astype(bool)

    # Extract values from valid voxels
    exp_img_valid = exp_img[valid_voxels]
    img_valid = img[valid_voxels]

    # Number of valid voxels
    n_of_voxels = exp_img_valid.size

    # Check if there are enough valid voxels for correlation
    if exp_img_valid.size < 2:
        raise ValueError("\n    [red1]Not enough valid voxels to perform correlation\n")

    # Perform Pearson correlation
    correlation, p_value = pearsonr(exp_img_valid, img_valid)
    
    return correlation, p_value, exp_img_valid, img_valid, n_of_voxels


def color_voxels_by_region(atlas_img, valid_voxels, region_csv_path):
    """Color valid voxels based on their region IDs using RGB values from a CSV file."""
    # Load region data from CSV
    region_df = pd.read_csv(region_csv_path, usecols=['Region_ID', 'R', 'G', 'B'])
    
    # Create an empty array to store the RGB colors for each voxel
    rgb_colors = np.zeros((np.count_nonzero(valid_voxels), 3))

    # Get the region IDs corresponding to the valid voxels
    region_ids = atlas_img[valid_voxels]

    # Assign RGB colors based on region ID
    for idx, region_id in enumerate(region_ids):
        # Get the RGB values for the current region
        region_color = region_df[region_df['Region_ID'] == region_id][['R', 'G', 'B']].values
        if region_color.size > 0:
            # Normalize the RGB values (0-255 to 0-1 range for matplotlib)
            rgb_colors[idx] = region_color[0] / 255.0

    return rgb_colors


def plot_correlation(expression_series, p_series, correlation, p_value, plot_title='Correlation Scatter Plot', rgb_colors=None, y_label='Statistical Map'):
    """Generate a scatter plot for the given expression and a stats value series, with a trend line and colored points."""
    plt.figure(figsize=(8, 6))

    # Scatter plot with RGB colors
    if rgb_colors is not None:
        plt.scatter(expression_series, p_series, color=rgb_colors, alpha=0.7, label='Data points')
    else:
        plt.scatter(expression_series, p_series, color='blue', alpha=0.7, label='Data points')

    # Fit and plot the trend line
    z = np.polyfit(expression_series, p_series, 1)
    p = np.poly1d(z)
    plt.plot(expression_series, p(expression_series), color='black', linestyle='-', label='Trend line')

    # Add a horizontal dashed line
    # plt.axhline(y=0.95, color='grey', linestyle='--', label='1-p = 0.95')

    # Add titles and labels
    plt.title(f'{plot_title}\nPearson r: {correlation:.2f}, p-value: {p_value:.2e}')
    plt.xlabel('Gene Expression')
    plt.ylabel(y_label)
    
    # Remove grid lines within the graph
    plt.grid(False)

    # Show the legend for the data points, trend line, and horizontal line
    plt.legend()

    # Save and show the plot
    plt.tight_layout()
    plt.savefig('correlation_scatter.png')
    plt.show()




@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load Htr2a expression and 3D map NIfTI files
    exp_img = load_nii(args.exp_map)
    img = load_nii(args.input)

    # Load masks if provided
    mask_list = []
    if args.masks:
        for mask_path in args.masks:
            mask_list.append(load_mask(mask_path))

    if args.regional and args.atlas:
        atlas_img = load_nii(args.atlas)
        # Compute the region-wise correlation
        correlation, p_value, merged_df, n_of_voxels = compute_regionwise_correlation(exp_img, img, atlas_img, mask_list, args.regions)

    else:
        # Compute the voxel-wise correlation
        correlation, p_value, exp_img_valid, img_valid, n_of_voxels = compute_voxelwise_correlation(exp_img, img, mask_list)

    # Output the result
    # print(f"\n    Pearson correlation: {correlation}")
    # print(f"    p-value: {p_value}")
    # print(f"    Number of voxels: {n_of_voxels}\n")
    print(f"Pearson correlation,{correlation}")
    print(f"p-value,{p_value}")
    print(f"Number of voxels,{n_of_voxels}")



    # Plot the correlation scatter plot
    if args.plot:
        if args.regional and args.atlas:
            # if args.csv_path == 'CCFv3-2017_regional_summary.csv' or args.csv_path == 'CCFv3-2020_regional_summary.csv':
            #     region_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path, usecols=['Region_ID', 'R', 'G', 'B'])
            # else:
            #     region_df = pd.read_csv(args.csv_path, usecols=['Region_ID', 'R', 'G', 'B'])
            region_df = pd.read_csv(args.csv_path, usecols=['Region_ID', 'R', 'G', 'B'])

            # Rename "Region_ID" to "Region" for merging
            region_df = region_df.rename(columns={'Region_ID': 'Region'})

            # Merge the results with the region data
            merged_df = pd.merge(merged_df, region_df, on='Region')

            # Convert the R, G, B values into a format usable for matplotlib
            rgb_colors = merged_df[['R', 'G', 'B']].values / 255.0

            plot_title = 'Region-wise Correlation Scatter Plot'
            plot_correlation(merged_df['Mean_Expression'], merged_df['Mean_Stat'], correlation, p_value, plot_title, rgb_colors=rgb_colors, y_label=args.y_label)
        else:
            if args.atlas:
                # Load the atlas image
                atlas_img = load_nii(args.atlas)

                # Check for valid voxels in both images
                valid_voxels = np.ones(exp_img.shape, dtype=bool)
                if mask_list:
                    for mask_data in mask_list:
                        valid_voxels = valid_voxels & mask_data.astype(bool)

                # Color the valid voxels based on their region using the atlas and CSV
                rgb_colors = color_voxels_by_region(atlas_img, valid_voxels=valid_voxels, region_csv_path=args.csv_path)
        
                # Plot the voxel-wise correlation with RGB colors
                plot_title = 'Voxel-wise Correlation Scatter Plot'
                plot_correlation(exp_img_valid, img_valid, correlation, p_value, plot_title, rgb_colors=rgb_colors, y_label=args.y_label)
            else:
                plot_title = 'Voxel-wise Correlation Scatter Plot'
                plot_correlation(exp_img_valid, img_valid, correlation, p_value, plot_title, y_label=args.y_label)

    verbose_end_msg()

if __name__ == '__main__':
    main()