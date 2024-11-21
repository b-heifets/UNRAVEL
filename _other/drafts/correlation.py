#!/usr/bin/env python3

"""
Use ``_other/drafts/correlation.py`` from UNRAVEL to calculate the region-wise or voxel-wise correlation between two images.

Note:
    - If an atlas is provided, the script will calculate the region-wise correlation.
    - For processing specific regions, modify with atlas with ``img_modify_labels``.
    - If no atlas is provided, the script will calculate the voxel-wise correlation.
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020_regional_summary.csv
    - It has columns: Region_ID, ID_Path, Region, Abbr, General_Region, R, G, B
    - Alternatively, use CCFv3-2017_regional_summary.csv or provide a custom CSV with the same columns.
    
Usage:
------
    _other/drafts/correlation.py -x path/x_axis_image.nii.gz -y path/y_axis_image.nii.gz [-mas path/mask1.nii.gz path/mask2.nii.gz] [-a path/atlas.nii.gz] [-r 1 2 3] [-csv path/CCFv3-2020_regional_summary.csv] [-v]
"""

import matplotlib.pyplot as plt
import mplcursors
import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.stats import pearsonr

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.core.img_io import load_nii
from unravel.region_stats.rstats_mean_IF import calculate_mean_intensity
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-x', '--x_image', help='path/x_axis_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-y', '--y_image', help='path/y_axis_image.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-mas', '--masks', help='Paths to mask .nii.gz files to restrict analysis. Default: None', nargs='*', default=None, action=SM)
    opts.add_argument('-a', '--atlas', help='Path to the atlas NIfTI file for a region-wise correlation. Default: None', default=None, action=SM)
    opts.add_argument('-rw', '--regional', help='Region-wise correlation. Default: False', action='store_true', default=False)
    opts.add_argument('-oc', '--output', help='path/output.csv', default=None, action=SM)
    opts.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020_regional_summary.csv', default='/Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/unravel/core/csvs/CCFv3-2020_regional_summary.csv', action=SM)
    opts.add_argument('-p', '--plot', help='Plot correlation. Default: False', action='store_true', default=False)
    opts.add_argument('-xl', '--x_label', help='X-axis label for the correlation plot. Default: "Image X mean intensity"', default='Image X mean intensity', action=SM)
    opts.add_argument('-yl', '--y_label', help='Y-axis label for the correlation plot. Default: "Image Y mean intensity"', default='Image Y mean intensity', action=SM)
    opts.add_argument('-xr', '--x_range', help='X-axis range for the correlation plot. (e.g., -1 1)', nargs=2, type=float, default=None, action=SM)
    opts.add_argument('-yr', '--y_range', help='Y-axis range for the correlation plot. (e.g., -1 1)', nargs=2, type=float, default=None, action=SM)
    opts.add_argument('-min', '--min_voxels', help='Minimum number of voxels per region.', type=int, default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Change /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/unravel/core/csvs/CCFv3-2020_regional_summary.csv to CCFv3-2020_regional_summary.csv after testing


def compute_regionwise_correlation(imgX, imgY, atlas_img, mask_list=None, min_voxels=None, verbose=False):
    """Compute region-wise correlation between two images, restricted by masks and region IDs."""
    # Apply mask(s) if provided
    valid_voxels = np.ones(imgY.shape, dtype=bool)
    if mask_list:
        for mask_data in mask_list:
            valid_voxels = valid_voxels & mask_data.astype(bool)

    # Mask the images to keep only valid voxels
    imgX_masked = np.where(valid_voxels, imgX, 0)
    imgY_masked = np.where(valid_voxels, imgY, 0)
    atlas_img_masked = np.where(valid_voxels, atlas_img, 0)

    # Get unique region IDs from the atlas image
    unique_regions = np.unique(atlas_img_masked)

    # Calculate the mean intensity of the images in each region
    imgX_mean_intensities_dict = calculate_mean_intensity(atlas_img_masked, imgX_masked, regions=unique_regions, verbose=verbose)
    imgY_mean_intensities_dict = calculate_mean_intensity(atlas_img_masked, imgY_masked, regions=unique_regions, verbose=verbose)

    # Convert the dictionaries to DataFrames
    imgX_df = pd.DataFrame(imgX_mean_intensities_dict.items(), columns=['Region', 'ImgX_Mean'])
    imgY_df = pd.DataFrame(imgY_mean_intensities_dict.items(), columns=['Region', 'ImgY_Mean'])

    # Merge the DataFrames on the region column
    merged_df = pd.merge(imgX_df, imgY_df, on='Region')

    # Drop regions with fewer than min_voxels voxels
    if min_voxels is not None:
        region_volumes = {region: np.count_nonzero(atlas_img_masked == region) for region in unique_regions}
        merged_df = merged_df[merged_df['Region'].map(region_volumes) >= min_voxels]

    # Compute the Pearson correlation between the mean intensities
    correlation, p_value = pearsonr(merged_df['ImgX_Mean'], merged_df['ImgY_Mean'])

    # Number of regions
    n_of_regions = merged_df.shape[0]

    return correlation, p_value, merged_df, n_of_regions

def compute_voxelwise_correlation(imgX, imgY, mask_list=None):
    """Compute voxel-wise correlation between two images, restricted by masks."""

    # Check that the images have the same shape
    if imgX.shape != imgY.shape:
        raise ValueError("\n    [red1]The two images must have the same shape\n")

    # Apply mask(s) if provided
    valid_voxels = np.ones(imgX.shape, dtype=bool)
    if mask_list:
        for mask_data in mask_list:
            valid_voxels = valid_voxels & mask_data.astype(bool)

    # Extract values from valid voxels
    imgX_valid = imgX[valid_voxels]
    imgY_valid = imgY[valid_voxels]

    # Number of valid voxels
    n_of_voxels = valid_voxels.size

    # Check if there are enough valid voxels for correlation
    if n_of_voxels < 2:
        raise ValueError("\n    [red1]Not enough valid voxels to perform correlation\n")

    # Perform Pearson correlation
    correlation, p_value = pearsonr(imgX_valid, imgY_valid)
    
    return correlation, p_value, imgX_valid, imgY_valid, n_of_voxels


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

def toggle_hover_visibility(event):
    global show_annotations
    if event.key == 'v':  # Press 'v' to toggle visibility
        show_annotations = not show_annotations

def plot_correlation(imgX_valid, imgY_valid, correlation, p_value, plot_title='Correlation Scatter Plot', rgb_colors=None, x_label=None, y_label=None, x_range=None, y_range=None, abbreviations=None):
    """Generate a scatter plot for the correlation between two images with hover functionality."""

    global show_annotations
    show_annotations = True  # Initialize the toggle variable

    plt.figure(figsize=(6, 6))

    # Scatter plot with RGB colors
    if rgb_colors is not None:
        scatter = plt.scatter(imgX_valid, imgY_valid, color=rgb_colors, alpha=0.7, label='Data points')
    else:
        scatter = plt.scatter(imgX_valid, imgY_valid, color='blue', alpha=0.7, label='Data points')

    # Fit and plot the trend line
    z = np.polyfit(imgX_valid, imgY_valid, 1)
    p = np.poly1d(z)
    plt.plot(imgX_valid, p(imgX_valid), color='black', linestyle='-', label='Trend line')

    # Add titles and labels
    plt.title(f'{plot_title}\nPearson r: {correlation:.2f}, p-value: {p_value:.2e}')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    
    # Remove grid lines within the graph
    plt.grid(False)

    # Get default axis limits only if x_range or y_range is not provided
    if x_range is None:
        x_range = plt.xlim()
        if x_range[0] < 0 and np.min(imgX_valid) > 0:
            x_range = (0, x_range[1])
        plt.xlim(x_range)
    if y_range is None:
        y_range = plt.ylim()
        if y_range[0] < 0 and np.min(imgY_valid) > 0:
            y_range = (0, y_range[1])
        plt.ylim(y_range)

    # Add dashed lines at y=0 and x=0 if ranges include 0
    if x_range[0] < 0:
        plt.axvline(0, color='grey', linestyle='--')
    if y_range[0] < 0:
        plt.axhline(0, color='grey', linestyle='--')

    # Enable hover interaction
    cursor = mplcursors.cursor(scatter, hover=True)
    
    # Customize hover annotation for each data point
    @cursor.connect("add")
    def on_add(sel):
        if show_annotations:
            x, y = imgX_valid[sel.index], imgY_valid[sel.index]
            abbr = abbreviations[sel.index] if abbreviations is not None else "N/A"
            sel.annotation.set_text(f'X: {x:.2f}\nY: {y:.2f}\nR: {abbr}')
            sel.annotation.get_bbox_patch().set(fc="lightgrey", alpha=0.8)
        else:
            sel.annotation.set_visible(False)  # Hide annotation if toggle is off

    # Connect key press event for toggling
    plt.gcf().canvas.mpl_connect('key_press_event', toggle_hover_visibility)

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

    imgX = load_nii(args.x_image)
    imgY = load_nii(args.y_image)

    # Load masks if provided
    mask_list = []
    if args.masks:
        for mask_path in args.masks:
            mask_list.append(load_mask(mask_path))

    if args.regional and args.atlas:
        atlas_img = load_nii(args.atlas)
        # Compute the region-wise correlation
        correlation, p_value, merged_df, n = compute_regionwise_correlation(imgX, imgY, atlas_img, mask_list, args.min_voxels, args.verbose)

    else:
        # Compute the voxel-wise correlation
        correlation, p_value, imgX_valid, imgY_valid, n = compute_voxelwise_correlation(imgX, imgY, mask_list)

    # Output the result
    # print(f"\n    Pearson correlation: {correlation}")
    # print(f"    p-value: {p_value}")
    # print(f"    Number of voxels: {n_of_voxels}\n")
    print(f'Min_voxels,{args.min_voxels}')
    print(f"Pearson correlation,{correlation}")
    print(f"p-value,{p_value}")
    print(f"Number of data points,{n}")

    if args.output:
        # Save the image names and correlation results to a CSV file
        result_df = pd.DataFrame({
            'Image X': [str(Path(args.x_image).name)],
            'Image Y': [str(Path(args.y_image).name)],
            'Pearson correlation': [correlation],
            'p-value': [p_value],
        })
        result_df.to_csv(args.output_csv, index=False)

    # Plot the correlation scatter plot
    if args.plot:
        if args.regional and args.atlas:
            # if args.csv_path == 'CCFv3-2017_regional_summary.csv' or args.csv_path == 'CCFv3-2020_regional_summary.csv':
            #     region_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path, usecols=['Region_ID', 'R', 'G', 'B'])
            # else:
            #     region_df = pd.read_csv(args.csv_path, usecols=['Region_ID', 'R', 'G', 'B'])
            region_df = pd.read_csv(args.csv_path, usecols=['Region_ID', 'R', 'G', 'B', 'Abbr'])

            # Rename "Region_ID" to "Region" for merging
            region_df = region_df.rename(columns={'Region_ID': 'Region'})

            # Merge the results with the region data
            merged_df = pd.merge(merged_df, region_df, on='Region')

            # Convert R, G, B to RGB colors and retrieve Abbr column as a list
            rgb_colors = merged_df[['R', 'G', 'B']].values / 255.0
            abbreviations = merged_df['Abbr'].tolist()

            plot_title = 'Region-wise Correlation'
            plot_correlation(merged_df['ImgX_Mean'], merged_df['ImgY_Mean'], correlation, p_value, plot_title, rgb_colors=rgb_colors, x_label=args.x_label, y_label=args.y_label, x_range=args.x_range, y_range=args.y_range, abbreviations=abbreviations)
        else:
            if args.atlas:
                # Load the atlas image
                atlas_img = load_nii(args.atlas)

                # Check for valid voxels in both images
                valid_voxels = np.ones(imgX.shape, dtype=bool)
                if mask_list:
                    for mask_data in mask_list:
                        valid_voxels = valid_voxels & mask_data.astype(bool)

                # Color the valid voxels based on their region using the atlas and CSV
                rgb_colors = color_voxels_by_region(atlas_img, valid_voxels=valid_voxels, region_csv_path=args.csv_path)
        
                # Plot the voxel-wise correlation with RGB colors
                plot_title = 'Voxel-wise Correlation'

                plot_correlation(imgX_valid, imgY_valid, correlation, p_value, plot_title, rgb_colors=rgb_colors, x_label=args.x_label, y_label=args.y_label, x_range=args.x_range, y_range=args.y_range)
            else:
                plot_title = 'Voxel-wise Correlation'
                plot_correlation(imgX_valid, imgY_valid, correlation, p_value, plot_title, x_label=args.x_label, y_label=args.y_label, x_range=args.x_range, y_range=args.y_range)

    verbose_end_msg()

if __name__ == '__main__':
    main()