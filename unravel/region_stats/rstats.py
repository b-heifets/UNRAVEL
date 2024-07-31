#!/usr/bin/env python3

"""
Use ``rstats`` from UNRAVEL to quantify cell or label densities for all regions in an atlas.

Usage if the atlas is already in native space from ``warp_to_native``:
----------------------------------------------------------------------
    rstats -s rel_path/segmentation_image.nii.gz -a rel_path/native_atlas_split.nii.gz -c Saline --dirs sample14 sample36 

Usage if the native atlas is not available; it is not saved (faster):
---------------------------------------------------------------------
    rstats -s rel_path/segmentation_image.nii.gz -m path/atlas_split.nii.gz -c Saline --dirs sample14 sample36

Outputs:
    - CSV files in ./sample??/regional_stats/ with cell counts or volumes of segmented voxels, region volumes, and cell or label densities for each region
    - For cell counts, a CSV with cell centroids is also saved

Note: 
    - Regarding --type, alternatively use 'counts' or 'volumes' for object counts or regional volumes
    - CCFv3-2020__regionID_side_IDpath_region_abbr.csv is in UNRAVEL/unravel/core/csvs/
    - It has columns: Region_ID, Side, ID_path, Region, Abbr
    - Alternatively, use gubra__regionID_side_IDpath_region_abbr.csv or other region info CSVs

Prereqs: 
    - ``reg_prep``, ``reg``, and ``seg_ilastik``

Next steps:
    - Use ``utils_agg_files`` to aggregate the CSVs from sample directories to the current directory
    - Use ``rstats_summary`` to summarize the results
"""

import argparse
import cc3d
import numpy as np
import os
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, load_image_metadata_from_txt
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.warp.to_native import to_native


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-t', '--type', help='Type of measurement (options: counts, region_volumes, cell_densities [default], label_volumes, or label_densities)', default='cell_densities', action=SM)
    parser.add_argument('-c', '--condition', help='One word name for group (prepended to sample ID for rstats_summary)', required=True, action=SM)
    parser.add_argument('-s', '--seg_img_path', help='rel_path/segmentation_image.nii.gz (can be glob pattern)', required=True, action=SM)
    parser.add_argument('-a', '--atlas_path', help='rel_path/native_atlas_split.nii.gz (use this -a if this exists from ``warp_to_native``, otherwise use -m ; "split" == left label IDs increased by 20,000)', default=None, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/atlas_image.nii.gz to warp from atlas space', default=None, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: ./parameters/metadata.txt', default="./parameters/metadata.txt", action=SM)
    parser.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from registration. Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (reg). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020__regionID_side_IDpath_region_abbr.csv', default='CCFv3-2020__regionID_side_IDpath_region_abbr.csv', action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def get_atlas_region_at_coords(atlas, x, y, z):
    """"Get the ndarray atlas region intensity at the given coordinates"""
    return atlas[int(x), int(y), int(z)]

@print_func_name_args_times()
def count_cells_in_regions(sample_path, seg_img, atlas_img, connectivity, condition, region_info_df):
    """Count the number of cells in each region based on atlas region intensities
    
    Parameters:
    -----------
    - sample_path (Path): Path to the sample directory.
    - seg_img (ndarray): 3D numpy array with the segmented image.
    - atlas_img (ndarray): 3D numpy array with the atlas image.
    - connectivity (int): Connectivity for connected components. Options: 6, 18, or 26.
    - condition (str): Name of the group.
    - region_info_df (DataFrame): DataFrame with region information (Region_ID, Side, ID_path, Region, Abbr).

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

    # Convert the centroids ndarray to a dataframe
    centroids_df = pd.DataFrame(centroids, columns=['x', 'y', 'z'])
    
    # Get the region ID for each cell
    os.makedirs(sample_path / "regional_stats", exist_ok=True)
    centroids_df['Region_ID'] = centroids_df.apply(lambda row: get_atlas_region_at_coords(atlas_img, row['x'], row['y'], row['z']), axis=1)

    # Save the centroids as a CSV file
    sample_name = sample_path.name
    centroid_output_filename = f"{condition}_{sample_name}_cell_centroids.csv" if condition else f"{sample_name}_cell_centroids.csv"
    centroids_df.to_csv(sample_path / "regional_stats" / centroid_output_filename, index=False)

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
    output_path = sample_path / "regional_stats" / output_filename
    region_counts_df.to_csv(output_path, index=False)

    # Sort the dataframe by counts and print the top 10 with count > 0
    region_counts_df.sort_values(by=f'{condition}_{sample_name}', ascending=False, inplace=True)
    print(f"\n{region_counts_df[region_counts_df[f'{condition}_{sample_name}'] > 0].head(10)}\n")

    region_ids = region_info_df['Region_ID']

    print(f"    Saving region counts to {output_path}\n")

    return region_counts_df, region_ids

def calculate_regional_volumes(sample_path, atlas, region_ids, xy_res, z_res, condition, region_info_df):
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

    Returns:
    --------
    - regional_volumes_df (DataFrame): DataFrame with regional volumes in the last column (Region_ID, Side, ID_path, Region, Abbr, <condition>_<sample_name>).

    Output:
    -------
    - Saves the regional volumes as a CSV file in the sample directory (./sample??/regional_stats/)
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
    output_filename = f"{condition}_{sample_name}_regional_volumes.csv" if condition else f"{sample_name}_regional_volumes.csv"
    output_path = sample_path / "regional_stats" / output_filename
    regional_volumes_df.to_csv(output_path, index=False)
    print(f"    Saving regional volumes to {output_path}\n")

    return regional_volumes_df

def calculate_regional_densities(sample_path, regional_data_df, regional_volumes_df, condition, density_type='cell_densities'):
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
    - Saves the regional densities as a CSV file in the sample directory (./sample??/regional_stats/)
    """

    print(f"\n    Calculating regional {density_type}\n")

    # Merge the regional counts and volumes into a single dataframe
    sample_name = sample_path.name
    if density_type == 'cell_densities':
        regional_data_df[f'{condition}_{sample_name}_density'] = regional_data_df[f'{condition}_{sample_name}'] / regional_volumes_df[f'{condition}_{sample_name}']
    elif density_type == 'label_densities':
        regional_data_df[f'{condition}_{sample_name}_density'] = regional_data_df[f'{condition}_{sample_name}'] / regional_volumes_df[f'{condition}_{sample_name}'] * 100
    else:
        raise ValueError("Invalid density type. Use 'cell_densities' or 'label_densities'.")

    regional_densities_df = regional_data_df.fillna(0)

    # Save regional densities as a CSV file
    output_filename = f"{condition}_{sample_name}_regional_{density_type}.csv" if condition else f"{sample_name}_regional_{density_type}.csv"
    output_path = sample_path / "regional_stats" / output_filename
    regional_densities_df.sort_values(by='Region_ID', ascending=True, inplace=True)

    # Drop the data column
    regional_densities_df.drop(f'{condition}_{sample_name}', axis=1, inplace=True)

    # Rename the density column
    regional_densities_df.rename(columns={f'{condition}_{sample_name}_density': f'{condition}_{sample_name}'}, inplace=True)

    regional_densities_df.to_csv(output_path, index=False)
    print(f"    Saving regional {density_type} to {output_path}\n")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()

            # Define output
            output_dir = sample_path / "regional_stats"
            output_dir.mkdir(exist_ok=True, parents=True)
            output_filename = f"{args.condition}_{sample_path.name}_regional_{args.type}.csv" if args.condition else f"{sample_path.name}_regional_{args.type}.csv"
            output = output_dir / output_filename
            if output.exists():
                print(f"\n\n    {output.name} already exists for {sample_path.name}. Skipping.\n")
                continue

            # Load the segmentation image
            if args.type == 'counts' or args.type == 'cell_densities' or args.type == 'label_densities' or args.type == 'label_volumes':
                seg_img_path = next(sample_path.glob(str(args.seg_img_path)), None)
                if seg_img_path is None:
                    print(f"No files match the pattern {args.seg_img_path} in {sample_path}")
                    continue
                seg_img = load_3D_img(seg_img_path)

            # Load or generate the native atlas image
            if args.atlas_path is not None and Path(sample_path, args.atlas_path).exists():
                atlas_path = sample_path / args.atlas_path
                atlas_img = load_3D_img(atlas_path)
            elif args.moving_img is not None and Path(sample_path, args.moving_img).exists():
                fixed_reg_input = sample_path / args.reg_outputs / args.fixed_reg_in
                if not fixed_reg_input.exists():
                    fixed_reg_input = sample_path / args.reg_outputs / "autofl_50um_fixed_reg_input.nii.gz"
                atlas_img = to_native(sample_path, args.reg_outputs, fixed_reg_input, args.moving_img, args.metadata, args.reg_res, args.miracl, int(0), 'multiLabel', output=None)
            else:
                print("    [red1]Atlas image not found. Please provide a path to the atlas image or the moving image")
                import sys ; sys.exit()

            # Load the region information dataframe
            if args.csv_path == 'CCFv3-2020__regionID_side_IDpath_region_abbr.csv' or args.csv_path == 'gubra__regionID_side_IDpath_region_abbr.csv':
                region_info_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path)
            else:
                region_info_df = pd.read_csv(args.csv_path)

            # Count cells in regions
            if args.type == 'counts' or args.type == 'cell_densities':
                regional_counts_df, region_ids = count_cells_in_regions(sample_path, seg_img, atlas_img, args.connect, args.condition, region_info_df)

            # Calculate volumes of segmented voxels in regions
            if args.type == 'label_densities' or args.type == 'label_volumes':
                # Multiply the segmented image by the atlas image to get the segmented regions
                
                # Binarize the segmentation image if needed
                if np.max(seg_img) > 1:
                    seg_img[seg_img > 0] = 1

                # Multiply the segmented image by the atlas image
                segmented_regions = seg_img * atlas_img

                # Calculate the volume of each segmented region
                region_ids = region_info_df['Region_ID']
                regional_volumes_in_seg_df = calculate_regional_volumes(sample_path, segmented_regions, region_ids, xy_res, z_res, args.condition, region_info_df)

            # Calculate regional volumes
            if args.type == 'region_volumes' or args.type == 'cell_densities' or args.type == 'label_densities':

                # Calculate regional volumes
                region_ids = region_info_df['Region_ID']
                regional_volumes_df = calculate_regional_volumes(sample_path, atlas_img, region_ids, xy_res, z_res, args.condition, region_info_df)

            # Calculate regional cell densities
            if args.type == 'cell_densities':
                calculate_regional_densities(sample_path, regional_counts_df, regional_volumes_df, args.condition, density_type=args.type)
            
            # Calculate regional label densities
            if args.type == 'label_densities':
                calculate_regional_densities(sample_path, regional_volumes_in_seg_df, regional_volumes_df, args.condition, density_type=args.type)

            progress.update(task_id, advance=1)
    
    verbose_end_msg()
    

if __name__ == '__main__':
    main()