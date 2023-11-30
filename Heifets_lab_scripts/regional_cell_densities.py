#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
import cc3d
import numpy as np
import os
import pandas as pd
from unravel_config import Configuration
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Perform regional cell counting', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process.', nargs='*', default=None, metavar='')
    parser.add_argument('-s', '--seg_dir', help='Dir name for segmentation image. Default: ochann_seg_ilastik_1.', default='ochann_seg_ilastik_1', metavar='')
    parser.add_argument('-a', '--atlas', help='Dir name for atlas relative to ./sample??/. Default: atlas/native_atlas/native_gubra_ano_split_25um.nii.gz', default='atlas/native_atlas/native_gubra_ano_split_25um.nii.gz', metavar='')
    parser.add_argument('-o', '--output', help='path/name.csv. Default: region_cell_counts.csv', default='region_cell_counts.csv', metavar='')
    parser.add_argument('-c', '--condition', help='Short name for experimental groud for front of sample ID. Default: None', default=None, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, metavar='')
    parser.epilog = """Run from experiment folder containing sample?? folders. 
    inputs: ./sample??/ochann_seg_ilastik_1/sample??_ochann_seg_ilastik_1.nii.gz & atlas/native_atlas/native_gubra_ano_split_25um.nii.gz (from to_native2.sh)
    gubra__regionID_side_IDpath_region_abbr.csv should be in the same dir as this script"""
    return parser.parse_args()


def get_atlas_region_at_coords(atlas, x, y, z):
    """"Get the ndarray atlas region intensity at the given coordinates"""
    return atlas[int(x), int(y), int(z)]


@print_func_name_args_times()
def count_cells_in_regions(sample, seg_img_path, atlas_path, connectivity, condition):
    """Count the number of cells in each region based on atlas region intensities"""

    img = load_3D_img(seg_img_path)

    atlas, xy_res, z_res = load_3D_img(atlas_path, return_res=True)

    # Check that the image and atlas have the same shape
    if img.shape != atlas.shape:
        raise ValueError(f"    [red1]Image and atlas have different shapes: {img.shape} != {atlas.shape}")

    # If the data is big-endian, convert it to little-endian
    if img.dtype.byteorder == '>':
        img = img.byteswap().newbyteorder()
    img = img.astype(np.uint8)

    labels_out, n = cc3d.connected_components(img, connectivity=connectivity, out_dtype=np.uint32, return_N=True)

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
    centroids_df['Region_ID'] = centroids_df.apply(lambda row: get_atlas_region_at_coords(atlas, row['x'], row['y'], row['z']), axis=1)

    # Count how many centroids are in each region
    print("    Counting cells in each region")
    region_counts_series = centroids_df['Region_ID'].value_counts()

    # Get the sample name from the sample directory
    sample_name = Path(sample).resolve().name

    # Add column header to the region counts
    region_counts_series = region_counts_series.rename_axis('Region_ID').reset_index(name=f'{condition}_{sample_name}')

    # Load csv with region IDs, sides, names, abbreviations, and sides
    region_info_df = pd.read_csv(Path(__file__).parent / 'gubra__regionID_side_IDpath_region_abbr.csv')

    # Merge the region counts into the region information dataframe
    region_counts_df = region_info_df.merge(region_counts_series, on='Region_ID', how='left')

    # After merging, fill NaN values with 0 for regions without any cells
    region_counts_df[f'{condition}_{sample_name}'].fillna(0, inplace=True)
    region_counts_df[f'{condition}_{sample_name}'] = region_counts_df[f'{condition}_{sample_name}'].astype(int)

    # Save the region counts as a CSV file
    os.makedirs(Path(sample).resolve() / "regional_cell_densities", exist_ok=True)
    output_filename = f"{condition}_{sample_name}_regional_cell_counts.csv" if condition else f"{sample_name}_regional_cell_counts.csv"
    output_path = Path(sample).resolve() / "regional_cell_densities" / output_filename
    region_counts_df.to_csv(output_path, index=False)

    # Sort the dataframe by counts and print the top 10 with count > 0
    region_counts_df.sort_values(by=f'{condition}_{sample_name}', ascending=False, inplace=True)
    print(f"\n{region_counts_df[region_counts_df[f'{condition}_{sample_name}'] > 0].head(10)}\n")

    region_ids = region_info_df['Region_ID']

    print(f"    Saving region counts to {output_path}\n")

    return region_counts_df, region_ids, atlas, xy_res, z_res


def calculate_regional_volumes(sample, atlas, region_ids, xy_res, z_res, condition):
    """Calculate volumes for given regions in an atlas image."""

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
    region_info_df = pd.read_csv(Path(__file__).parent / 'gubra__regionID_side_IDpath_region_abbr.csv')
    sample_name = Path(sample).resolve().name
    region_info_df[f'{condition}_{sample_name}'] = region_info_df['Region_ID'].map(regional_volumes)
    regional_volumes_df = region_info_df.fillna(0)

    # Save regional volumes as a CSV file
    output_filename = f"{condition}_{sample_name}_regional_volumes.csv" if condition else f"{sample_name}_regional_volumes.csv"
    output_path = Path(sample).resolve() / "regional_cell_densities" / output_filename
    regional_volumes_df.to_csv(output_path, index=False)
    print(f"    Saving regional volumes to {output_path}\n")

    return regional_volumes_df

# Function to calculate regional cell densities
def calculate_regional_cell_densities(sample, regional_counts_df, regional_volumes_df, condition):
    """Calculate cell densities for each region in the atlas."""

    print("\n    Calculating regional cell densities\n")

    # Merge the regional counts and volumes into a single dataframe
    sample_name = Path(sample).resolve().name
    regional_counts_df[f'{condition}_{sample_name}_density'] = regional_counts_df[f'{condition}_{sample_name}'] / regional_volumes_df[f'{condition}_{sample_name}']
    regional_densities_df = regional_counts_df.fillna(0)

    # Save regional cell densities as a CSV file
    output_filename = f"{condition}_{sample_name}_regional_cell_densities.csv" if condition else f"{sample_name}_regional_cell_densities.csv"
    output_path = Path(sample).resolve() / "regional_cell_densities" / output_filename
    regional_densities_df.sort_values(by='Region_ID', ascending=True, inplace=True)

    # Drop the count column
    regional_densities_df.drop(f'{condition}_{sample_name}', axis=1, inplace=True)

    # Rename the density column
    regional_densities_df.rename(columns={f'{condition}_{sample_name}_density': f'{condition}_{sample_name}'}, inplace=True)

    regional_densities_df.to_csv(output_path, index=False)
    print(f"    Saving regional cell densities to {output_path}\n")



def main():

    samples = get_samples(args.dirs, args.pattern)
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            sample_name = Path(sample).resolve().name
            seg_img_path = Path(sample).resolve() / args.seg_dir / f"{sample_name}_{args.seg_dir}.nii.gz"
            atlas_path = Path(sample).resolve() / args.atlas

            # Count cells in regions
            regional_counts_df, region_ids, atlas, xy_res, z_res = count_cells_in_regions(sample, seg_img_path, atlas_path, args.connect, args.condition)

            # Calculate regional volumes
            regional_volumes_df = calculate_regional_volumes(sample, atlas, region_ids, xy_res, z_res, args.condition)

            # Calculate regional cell densities
            calculate_regional_cell_densities(sample, regional_counts_df, regional_volumes_df, args.condition)

            progress.update(task_id, advance=1)
    
    
if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()