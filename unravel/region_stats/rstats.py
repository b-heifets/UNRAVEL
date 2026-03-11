#!/usr/bin/env python3

"""
Use ``rstats`` from UNRAVEL to quantify region-wise metrics in an atlas.

Supported metrics:
    - counts
    - region_volumes
    - cell_densities
    - label_volumes
    - label_densities
    - mean_in_region
    - mean_in_seg_in_region

Prereqs: 
    - ``reg_prep``, ``reg``, and optionally ``seg_ilastik``

Inputs:
    - For counts / cell_densities / label_volumes / label_densities:
        - rel_path/segmentation_image.nii.gz (can be glob pattern)
    - For mean_in_region / mean_in_seg_in_region:
        - rel_path/intensity_image (e.g., .nii.gz, .tif, .ome.tif, .czi, .zarr, .h5, or dir of tifs)
    - rel_path/native_atlas_split.nii.gz (use this -a if this exists from ``warp_to_native``; otherwise, use -m to warp atlas to native space)

Outputs:
    - CSV files in ./sample??/<output_dir>/ (default: regional_stats)
    - Example CSV naming: <condition>_sample??_cell_densities.csv or <condition>_sample??_mean_in_region.csv
    - For mean-based metrics, CSVs include both a support column and the mean value column

Note: 
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020__regionID_side_IDpath_region_abbr.csv
    - Columns in region info CSV: Region_ID, Side, ID_Path, Region, Abbr
    - If using serial-2 photon data, use the --stpt flag to interleave blank slices to prevent cells from fusing across slices during counting

Next steps:
    - Use ``utils_agg_files`` to aggregate the CSVs from sample directories to the current directory
    - Use ``rstats_summary`` to summarize the results

Usage if the atlas is already in native space from ``warp_to_native``:
----------------------------------------------------------------------
    rstats -s rel_path/segmentation_image.nii.gz -a rel_path/native_atlas_split.nii.gz -c Saline --dirs sample14 sample36 [-2p] [-t cell_densities] [-md parameters/metadata.txt] [-cc 6] [-ro reg_outputs] [-fri autofl_50um_masked_fixed_reg_input.nii.gz] [-r 50] [-csv CCFv3-2020__regionID_side_IDpath_region_abbr.csv] [-mi] [-d list of paths] [-p sample??] [-v]

Usage if the native atlas is not available; it is not saved (faster):
---------------------------------------------------------------------
    rstats -s rel_path/segmentation_image.nii.gz -m path/atlas_split.nii.gz -c Saline --dirs sample14 sample36 [-2p] [-t cell_densities] [-md parameters/metadata.txt] [-cc 6] [-ro reg_outputs] [-fri autofl_50um_masked_fixed_reg_input.nii.gz] [-r 50] [-csv CCFv3-2020__regionID_side_IDpath_region_abbr.csv] [-mi] [-d list of paths] [-p sample??] [-v]

Usage for mean intensity only within segmented voxels in each region:
---------------------------------------------------------------------
    rstats -t mean_in_seg_in_region -s iba1_seg/iba1_seg_1.nii.gz -i iba1_rb20 -m path/atlas_split.nii.gz -c Saline -d <Path to dir with Saline samples>
"""

import cc3d
import numpy as np
import os
import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt
from unravel.core.utils import get_pad_percent, log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.warp.to_native import to_native


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-c', '--condition', help='One word name for group (prepended to sample ID for rstats_summary)', required=True, action=SM)

    key_opts = parser.add_argument_group('Key options')
    key_opts.add_argument('-s', '--seg_img_path', help='rel_path/segmentation_image.nii.gz (can be glob pattern) for counts, label volumes/densities, or mean in the segmentation mask', action=SM)
    key_opts.add_argument('-a', '--atlas_path', help='rel_path/native_atlas_split.nii.gz (use this -a if this exists from ``warp_to_native``, otherwise use -m ; "split" == left label IDs increased by 20,000)', default=None, action=SM)
    key_opts.add_argument('-m', '--moving_img', help='path/atlas_image.nii.gz to warp from atlas space', default=None, action=SM)
    key_opts.add_argument('-t', '--type', help='Type of measurement (counts, region_volumes, cell_densities \[default], label_volumes, label_densities, mean_in_region, or mean_in_seg_in_region)', default='cell_densities', choices=['counts', 'region_volumes', 'cell_densities', 'label_volumes', 'label_densities', 'mean_in_region', 'mean_in_seg_in_region'], action=SM)
    key_opts.add_argument('-2p', '--stpt', help='For serial-2 photon data, use this flag to interleave blank slices (prevents cells from fusing across slices during counting). Only use with -t <counts or cell_densities>.', action='store_true', default=False)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output_dir', help='Output subdirectory within each sample directory. Default: regional_stats', default='regional_stats', action=SM)
    opts.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, action=SM)
    opts.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from registration. Default: reg_outputs", default="reg_outputs", action=SM)
    opts.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (reg). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    opts.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020__regionID_side_IDpath_region_abbr.csv', default='CCFv3-2020__regionID_side_IDpath_region_abbr.csv', action=SM)
    opts.add_argument('-pad', '--pad_percent', help='Padding percentage from ``reg``. Default: from parameters/pad_percent.txt or 0.25.', type=float, action=SM)
    opts.add_argument('-min', '--min_voxels', help='Minimum voxel count per connected component to keep (default: 1 keeps all)', type=int, default=1, action=SM)
    opts.add_argument('-i', '--intensity_img', help='rel_path/intensity image used for mean_in_region or mean_in_seg_in_region', default=None, action=SM)
    opts.add_argument('-ch', '--channel', help='Channel number for .czi images. Default: 0', default=0, type=int, action=SM)

    compatibility = parser.add_argument_group('Compatibility options')
    compatibility.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Using the sample_key.csv would be better for batch processing than using -c for the condition.
# TODO: Check other parameters of cc3d.connected_components to see if processing can be sped up (e.g., binary_image=True; may need to update cc3d first)

def get_atlas_region_at_coords(atlas, x, y, z):
    """"Get the ndarray atlas region intensity at the given coordinates"""
    return atlas[int(x), int(y), int(z)]

@print_func_name_args_times()
def count_cells_in_regions(sample_path, seg_img, atlas_img, connectivity, condition, region_info_df, stpt=False, min_voxels=1, output_dir_name='regional_stats'):
    """Count the number of cells in each region based on atlas region intensities
    
    Parameters:
    -----------
    - sample_path (Path): Path to the sample directory.
    - seg_img (ndarray): 3D numpy array with the segmented image.
    - atlas_img (ndarray): 3D numpy array with the atlas image.
    - connectivity (int): Connectivity for connected components. Options: 6, 18, or 26.
    - condition (str): Name of the group.
    - region_info_df (DataFrame): DataFrame with region information (Region_ID, Side, ID_path, Region, Abbr).
    - stpt (bool): Whether to account for interleaved blank slices (adjustment for serial-2 photon data).
    - min_voxels (int): Minimum voxel count per connected component to keep (default: 1 keeps all).

    Returns:
    --------
    - region_counts_df (DataFrame): DataFrame with regional cell counts in the last column (Region_ID, Side, ID_path, Region, Abbr, <condition>_<sample_name>).
    - region_ids (list): List of region IDs in the atlas.

    Output:
    -------
    - Saves the regional cell counts as a CSV file in the sample directory (./sample??/regional_stats/)
    """

    # Check that the image and atlas have the same shape
    if seg_img.shape != atlas_img.shape:
        raise ValueError(f"    [red1]Image and atlas have different shapes: {seg_img.shape} != {atlas_img.shape}")

    # If the data is big-endian, convert it to little-endian
    if seg_img.dtype.byteorder == '>':
        seg_img = seg_img.byteswap().newbyteorder()
    seg_img = seg_img.astype(np.uint8)

    labels_out, n = cc3d.connected_components(seg_img, connectivity=connectivity, out_dtype=np.uint32, return_N=True)

    print(f"\n    Total cell count: {n}\n")

    # Get cell coordinates from the labeled image
    print("    Getting cell coordinates")
    stats = cc3d.statistics(labels_out)

    # Convert the dictionary to a dataframe
    print("    Converting to dataframe")
    centroids = stats['centroids']

    # Drop the first row, which is the background
    centroids = np.delete(centroids, 0, axis=0)
    sizes = np.delete(stats['voxel_counts'], 0, axis=0)

    # Apply min_voxels threshold
    keep_mask = sizes >= min_voxels
    centroids = centroids[keep_mask]

    # Adjust z-coordinate if interleaving was applied
    if stpt:
        centroids[:, 2] /= 2.0

    # Convert the centroids ndarray to a dataframe
    centroids_df = pd.DataFrame(centroids, columns=['x', 'y', 'z'])
    
    # Get the region ID for each cell
    os.makedirs(sample_path / output_dir_name, exist_ok=True)
    centroids_df['Region_ID'] = centroids_df.apply(lambda row: get_atlas_region_at_coords(atlas_img, row['x'], row['y'], row['z']), axis=1)

    # Save the centroids as a CSV file
    sample_name = sample_path.name
    centroid_output_filename = f"{condition}_{sample_name}_cell_centroids.csv" if condition else f"{sample_name}_cell_centroids.csv"
    centroids_df.to_csv(sample_path / output_dir_name / centroid_output_filename, index=False)

    # Count how many centroids are in each region
    print("    Counting cells in each region")
    region_counts_series = centroids_df['Region_ID'].value_counts()

    # Add column header to the region counts
    region_counts_series = region_counts_series.rename_axis('Region_ID').reset_index(name=f'{condition}_{sample_name}')

    # Merge the region counts into the region information dataframe
    region_counts_df = region_info_df.merge(region_counts_series, on='Region_ID', how='left')

    # After merging, fill NaN values with 0 for regions without any cells
    region_counts_df[f'{condition}_{sample_name}'].fillna(0, inplace=True)
    region_counts_df[f'{condition}_{sample_name}'] = region_counts_df[f'{condition}_{sample_name}'].astype(int)

    # Save the region counts as a CSV file
    output_filename = f"{condition}_{sample_name}_regional_cell_counts.csv" if condition else f"{sample_name}_regional_cell_counts.csv"
    output_path = sample_path / output_dir_name / output_filename
    region_counts_df.to_csv(output_path, index=False)

    # Sort the dataframe by counts and print the top 10 with count > 0
    region_counts_df.sort_values(by=f'{condition}_{sample_name}', ascending=False, inplace=True)
    print(f"\n{region_counts_df[region_counts_df[f'{condition}_{sample_name}'] > 0].head(10)}\n")

    region_ids = region_info_df['Region_ID']

    print(f"    Saving region counts to {output_path}\n")

    return region_counts_df, region_ids


def calculate_regional_volumes(sample_path, atlas, region_ids, xy_res, z_res, condition, region_info_df, output_suffix='volumes', output_dir_name='regional_stats'):
    """Calculate volumes for given regions in an atlas image.
    
    Parameters:
    -----------
    - sample_path (Path): Path to the sample directory.
    - atlas (ndarray): 3D numpy array with the atlas image.
    - region_ids (list): List of region IDs to calculate volumes for.
    - xy_res (float): Resolution in the xy plane in microns.
    - z_res (float): Resolution in the z plane in microns.
    - condition (str): Name of the group.
    - region_info_df (DataFrame): DataFrame with region information (Region_ID, Side, ID_path, Region, Abbr).
    - output_suffix (str): Suffix for the output CSV file name (default: 'volumes').
    - output_dir_name (str): Name of the subdirectory within each sample directory to save the output CSV (default: 'regional_stats').

    Returns:
    --------
    - regional_volumes_df (DataFrame): DataFrame with regional volumes in the last column (Region_ID, Side, ID_path, Region, Abbr, <condition>_<sample_name>).

    Output:
    -------
    - Saves the regional volumes as a CSV file in the specified subdirectory within each sample directory.
    """

    print("\n    Calculating regional volumes\n")

    # Calculate the voxel volume in cubic millimeters
    voxel_volume = (xy_res * xy_res * z_res) / 1000**3

    # Use bincount to get counts for all intensities
    voxel_counts = np.bincount(atlas.flatten())

    # Ensure that region_ids are within the range of voxel_counts length
    region_ids = [rid for rid in region_ids if rid < len(voxel_counts)]

    # Map the counts to Region_IDs and calculate volumes
    regional_volumes = {region_id: voxel_counts[region_id] * voxel_volume for region_id in region_ids}

    # Merge the regional volumes into the region information dataframe
    sample_name = sample_path.name
    region_info_df[f'{condition}_{sample_name}'] = region_info_df['Region_ID'].map(regional_volumes)
    regional_volumes_df = region_info_df.fillna(0)

    # Save regional volumes as a CSV file
    output_filename = f"{condition}_{sample_name}_regional_{output_suffix}.csv" if condition else f"{sample_name}_regional_{output_suffix}.csv"

    output_path = sample_path / output_dir_name / output_filename
    regional_volumes_df.to_csv(output_path, index=False)
    print(f"    Saving regional {output_suffix} to {output_path}\n")


    return regional_volumes_df

def calculate_regional_densities(sample_path, regional_data_df, regional_volumes_df, condition, density_type='cell_densities', output_dir_name='regional_stats'):
    """Calculate cell or label densities for each region in the atlas.
    
    Parameters:
    -----------
    - sample_path (Path): Path to the sample directory.
    - regional_data_df (DataFrame): DataFrame with regional data (object counts or label volumes).
    - regional_volumes_df (DataFrame): DataFrame with regional volumes.
    - condition (str): Name of the group.
    - density_type (str): Type of density to calculate. Options: 'cell_densities' or 'label_densities'.
    
    Output:
    -------
    - Saves the regional densities as a CSV file in the specified subdirectory within each sample directory.
    - Columns: Region_ID, Side, ID_path, Region, Abbr, <condition>_<sample>_numerator, <condition>_<sample>_denominator, <condition>_<sample>
    - The numerator column contains the original counts or label volumes
    - The denominator column contains the regional volumes
    - The last column contains the calculated densities (cells per mm^3 for cell_densities or % volume for label_densities).
    """

    print(f"\n    Calculating regional {density_type}\n")

    sample_name = sample_path.name
    value_col = f'{condition}_{sample_name}'
    numerator_col = f'{condition}_{sample_name}_numerator'
    denominator_col = f'{condition}_{sample_name}_denominator'

    regional_densities_df = regional_data_df.copy()
    regional_densities_df[denominator_col] = regional_volumes_df[value_col]

    if density_type == 'cell_densities':
        regional_densities_df[numerator_col] = regional_data_df[value_col]
        regional_densities_df[value_col] = regional_densities_df[numerator_col] / regional_densities_df[denominator_col]

    elif density_type == 'label_densities':
        regional_densities_df[numerator_col] = regional_data_df[value_col]
        regional_densities_df[value_col] = regional_densities_df[numerator_col] / regional_densities_df[denominator_col] * 100

    else:
        raise ValueError("Invalid density type. Use 'cell_densities' or 'label_densities'.")

    regional_densities_df = regional_densities_df.fillna(0)
    regional_densities_df.sort_values(by='Region_ID', ascending=True, inplace=True)

    output_filename = f"{condition}_{sample_name}_regional_{density_type}.csv" if condition else f"{sample_name}_regional_{density_type}.csv"
    output_path = sample_path / output_dir_name / output_filename
    regional_densities_df.to_csv(output_path, index=False)

    print(f"    Saving regional {density_type} to {output_path}\n")


def interleave_blank_slices(img):
    """Interleave blank slices in a 3D image to prevent cells from fusing across slices during counting.

    Parameters:
        - img (ndarray): 3D numpy array with the image.

    Returns:
        - img_interleaved (ndarray): 3D numpy array with interleaved blank slices.
    """
    img_interleaved = np.zeros((img.shape[0], img.shape[1], img.shape[2]*2), dtype=img.dtype)
    img_interleaved[:, :, ::2] = img  # ::2 means every second slice
    return img_interleaved

def calculate_regional_means(sample_path, intensity_img, atlas_img, condition, region_info_df, mean_type='mean_in_region', seg_img=None, output_dir_name='regional_stats'):
    """Calculate region-wise mean intensity for each region or in segmentation mask within each region based on atlas region intensities.

    Parameters:
    -----------
        - sample_path (Path): Path to the sample directory.
        - intensity_img (ndarray): 3D image used for intensity measurements.
        - atlas_img (ndarray): 3D atlas image in native space.
        - condition (str): Group name.
        - region_info_df (DataFrame): Region metadata.
        - mean_type (str): 'mean_in_region' or 'mean_in_seg_in_region'
        - seg_img (ndarray or None): Segmentation mask required for mean_in_seg_in_region
        - output_dir_name (str): Name of the subdirectory within each sample directory to save the output CSV (default: 'regional_stats').

    Returns:
    --------
        - regional_means_df (DataFrame) with columns: Region_ID, Side, ID_path, Region, Abbr, <condition>_<sample_name>, <condition>_<sample_name>_support
        - Saves the regional means as a CSV file in the specified subdirectory within each sample directory. The CSV includes both the mean intensity values and the support (voxel counts) for each region.
    """

    if intensity_img.shape != atlas_img.shape:
        raise ValueError(f"    [red1]Intensity image and atlas have different shapes: {intensity_img.shape} != {atlas_img.shape}")

    if mean_type == 'mean_in_seg_in_region':
        if seg_img is None:
            raise ValueError("seg_img is required for mean_in_seg_in_region")
        if seg_img.shape != atlas_img.shape:
            raise ValueError(f"    [red1]Segmentation image and atlas have different shapes: {seg_img.shape} != {atlas_img.shape}")

    atlas_flat = atlas_img.ravel().astype(np.int64)
    intensity_flat = intensity_img.ravel().astype(np.float64)

    if mean_type == 'mean_in_seg_in_region':
        seg_mask = seg_img.ravel() > 0
        atlas_flat = atlas_flat[seg_mask]
        intensity_flat = intensity_flat[seg_mask]

    max_region_id = int(atlas_flat.max()) if atlas_flat.size else 0
    voxel_counts = np.bincount(atlas_flat, minlength=max_region_id + 1)
    intensity_sums = np.bincount(atlas_flat, weights=intensity_flat, minlength=max_region_id + 1)

    sample_name = sample_path.name
    value_col = f'{condition}_{sample_name}'
    support_col = f'{condition}_{sample_name}_support'

    regional_means = {}
    regional_support = {}
    for region_id in region_info_df['Region_ID']:
        if region_id < len(voxel_counts) and voxel_counts[region_id] > 0:
            regional_means[region_id] = intensity_sums[region_id] / voxel_counts[region_id]
            regional_support[region_id] = int(voxel_counts[region_id])
        else:
            regional_means[region_id] = np.nan
            regional_support[region_id] = 0

    regional_means_df = region_info_df.copy()
    regional_means_df[support_col] = regional_means_df['Region_ID'].map(regional_support).fillna(0).astype(int)
    regional_means_df[value_col] = regional_means_df['Region_ID'].map(regional_means)

    output_filename = f"{condition}_{sample_name}_regional_{mean_type}.csv" if condition else f"{sample_name}_regional_{mean_type}.csv"
    output_path = sample_path / output_dir_name / output_filename
    regional_means_df.to_csv(output_path, index=False)

    print(f"    Saving regional {mean_type} to {output_path}\n")
    return regional_means_df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.type in ['counts', 'cell_densities', 'label_volumes', 'label_densities', 'mean_in_seg_in_region'] and args.seg_img_path is None:
        raise ValueError(f"--seg_img_path is required for --type {args.type}")

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()

            # Define output
            output_dir = sample_path / args.output_dir
            output_dir.mkdir(exist_ok=True, parents=True)
            if args.type == 'counts':
                output_filename = f"{args.condition}_{sample_path.name}_regional_cell_counts.csv" if args.condition else f"{sample_path.name}_regional_cell_counts.csv"
            else:
                output_filename = f"{args.condition}_{sample_path.name}_regional_{args.type}.csv" if args.condition else f"{sample_path.name}_regional_{args.type}.csv"

            output = output_dir / output_filename
            if output.exists():
                print(f"\n\n    {output.name} already exists for {sample_path.name}. Skipping.\n")
                continue

            # Load the segmentation image
            seg_img = None
            if args.type in ['counts', 'cell_densities', 'label_densities', 'label_volumes', 'mean_in_seg_in_region']:

                seg_img_path = next(sample_path.glob(str(args.seg_img_path)), None)
                if seg_img_path is None:
                    print(f"No files match the pattern {args.seg_img_path} in {sample_path}")
                    continue
                seg_img = load_3D_img(seg_img_path, verbose=args.verbose)

                if args.stpt:
                    print(f"    Interleaving slices for serial-2 photon data to prevent cells from fusing across slices during counting")
                    seg_img = interleave_blank_slices(seg_img)

            # Load or generate the native atlas image
            if args.atlas_path is not None and Path(sample_path, args.atlas_path).exists():
                atlas_path = sample_path / args.atlas_path
                atlas_img = load_3D_img(atlas_path, verbose=args.verbose)
            elif args.moving_img is not None and Path(args.moving_img).exists():
                fixed_reg_input = sample_path / args.reg_outputs / args.fixed_reg_in
                if not fixed_reg_input.exists():
                    fixed_reg_input = sample_path / args.reg_outputs / "autofl_50um_fixed_reg_input.nii.gz"
                pad_percent = get_pad_percent(sample_path / args.reg_outputs, args.pad_percent)
                atlas_img = to_native(sample_path, args.reg_outputs, fixed_reg_input, args.moving_img, args.metadata, args.reg_res, args.miracl, int(0), 'multiLabel', output=None, pad_percent=pad_percent)
            else:
                print("    [red1]Atlas image not found. Please provide a path to the atlas image or the moving image")
                import sys ; sys.exit()

            if args.stpt:
                print(f"    Interleaving slices in atlas for serial-2 photon data to match segmentation image")
                atlas_img = interleave_blank_slices(atlas_img)

            intensity_img = None
            if args.type in ['mean_in_region', 'mean_in_seg_in_region']:
                if args.intensity_img is None:
                    raise ValueError("--intensity_img is required for mean_in_region or mean_in_seg_in_region.")

                if args.stpt:
                    # --stpt is not needed for mean_in_region or mean_in_seg_in_region.
                    raise ValueError("--stpt is not compatible with mean_in_region or mean_in_seg_in_region. This is because interleaving blank slices is only relevant for counting cells in segmentation masks, and does not apply to calculating mean intensities in regions. Please remove the --stpt flag when using mean-based metrics.")

                intensity_img_path = next(sample_path.glob(str(args.intensity_img)), None)
                if intensity_img_path is None:
                    print(f"No files match the pattern {args.intensity_img} in {sample_path}")
                    continue

                intensity_img = load_3D_img(intensity_img_path, channel=args.channel, verbose=args.verbose)

            # Load the region information dataframe
            if args.csv_path == 'CCFv3-2020__regionID_side_IDpath_region_abbr.csv' or args.csv_path == 'CCFv3-2017__regionID_side_IDpath_region_abbr.csv':
                region_info_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path)
            else:
                region_info_df = pd.read_csv(args.csv_path)

            # Count cells in regions
            if args.type == 'counts' or args.type == 'cell_densities':
                regional_counts_df, region_ids = count_cells_in_regions(sample_path, seg_img, atlas_img, args.connect, args.condition, region_info_df, stpt=args.stpt, min_voxels=args.min_voxels, output_dir_name=args.output_dir)

            # Calculate volumes of segmented voxels in regions
            if args.type == 'label_densities' or args.type == 'label_volumes':
                # Multiply the segmented image by the atlas image to get the segmented regions
                
                # Binarize the segmentation image if needed
                if np.max(seg_img) > 1:
                    seg_img[seg_img > 0] = 1

                # Multiply the segmented image by the atlas image
                segmented_regions = seg_img * atlas_img

                # Calculate the volume of each segmented region (z_res not changed by interleaving)
                region_ids = region_info_df['Region_ID']
                regional_volumes_in_seg_df = calculate_regional_volumes(sample_path, segmented_regions, region_ids, xy_res, z_res, args.condition, region_info_df, output_suffix='label_volumes', output_dir_name=args.output_dir)

            # Calculate regional volumes
            if args.type == 'region_volumes' or args.type == 'cell_densities' or args.type == 'label_densities':

                # Calculate regional volumes (z_res not changed by interleaving)
                region_ids = region_info_df['Region_ID']
                regional_volumes_df = calculate_regional_volumes(sample_path, atlas_img, region_ids, xy_res, z_res, args.condition, region_info_df, output_suffix='volumes', output_dir_name=args.output_dir)

            # Calculate regional cell densities
            if args.type == 'cell_densities':
                calculate_regional_densities(sample_path, regional_counts_df, regional_volumes_df, args.condition, density_type=args.type, output_dir_name=args.output_dir)
            
            # Calculate regional label densities
            if args.type == 'label_densities':
                calculate_regional_densities(sample_path, regional_volumes_in_seg_df, regional_volumes_df, args.condition, density_type=args.type, output_dir_name=args.output_dir)

            # Calculate regional means
            if args.type == 'mean_in_region':
                calculate_regional_means(sample_path, intensity_img, atlas_img, args.condition, region_info_df, mean_type='mean_in_region', seg_img=None, output_dir_name=args.output_dir)

            # Calculate regional means in segmentation mask within each region
            if args.type == 'mean_in_seg_in_region':
                calculate_regional_means(sample_path, intensity_img, atlas_img, args.condition, region_info_df, mean_type='mean_in_seg_in_region', seg_img=seg_img, output_dir_name=args.output_dir)

            progress.update(task_id, advance=1)
    
    verbose_end_msg()
    

if __name__ == '__main__':
    main()