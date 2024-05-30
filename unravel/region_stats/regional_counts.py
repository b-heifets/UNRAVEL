#!/usr/bin/env python3

import argparse
import cc3d
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.argparse_utils import SuppressMetavar, SM
from unravel.config import Configuration
from unravel.img_io import load_3D_img
from unravel.utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Perform regional cell counting', formatter_class=SuppressMetavar)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', action=SM)
    parser.add_argument('--dirs', help='List of folders to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-s', '--seg_dir', help='Dir name for segmentation image. Default: ochann_seg_ilastik_1.', default='ochann_seg_ilastik_1', action=SM)
    parser.add_argument('-a', '--atlas', help='Dir name for atlas relative to ./sample??/. Default: atlas/native_atlas/native_gubra_ano_split_25um.nii.gz', default='atlas/native_atlas/native_gubra_ano_split_25um.nii.gz', action=SM)
    parser.add_argument('-o', '--output', help='path/name.csv. Default: region_cell_counts.csv', default='region_cell_counts.csv', action=SM)
    parser.add_argument('-c', '--condition', help='Short name for experimental groud for front of sample ID. Default: None', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.add_argument('-cc', '--connect', help='Connected component connectivity (6, 18, or 26). Default: 6', type=int, default=6, action=SM)
    parser.epilog = "Run from experiment folder containing sample?? folders. Seg image: ./sample??/ochann_seg_ilastik_1/sample??_ochann_seg_ilastik_1.nii.gz"
    return parser.parse_args()


def get_atlas_region_at_coords(atlas, x, y, z):
    """"Get the ndarray atlas region intensity at the given coordinates"""
    return atlas[int(x), int(y), int(z)]

@print_func_name_args_times()
def count_cells_in_regions(sample, seg_img_path, atlas_path, connectivity, condition):
    """Count the number of cells in each region based on atlas region intensities"""

    img = load_3D_img(seg_img_path)
    atlas = load_3D_img(atlas_path)

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
    region_counts_series = region_counts_series.rename_axis('Region_ID').reset_index(name=f'{condition}_{sample_name}_Count')

    # Load csv with region IDs, sides, names, abbreviations, and sides
    region_info_df = pd.read_csv(Path(__file__).parent.parent / 'unravel' / 'csvs' / 'gubra__region_ID_side_name_abbr.csv')

    # Merge the region counts into the region information dataframe
    merged_df = region_info_df.merge(region_counts_series, on='Region_ID', how='left')

    # After merging, fill NaN values with 0 for regions without any cells
    merged_df[f'{condition}_{sample_name}_Count'].fillna(0, inplace=True)
    merged_df[f'{condition}_{sample_name}_Count'] = merged_df[f'{condition}_{sample_name}_Count'].astype(int)

    # Save the region counts as a CSV file
    output_filename = f"{condition}_{sample_name}_region_cell_counts.csv" if condition else f"{sample_name}_region_cell_counts.csv"
    output_path = Path(sample).resolve() / output_filename
    merged_df.to_csv(output_path, index=False)
    print(f"    Saving region counts to {output_path}\n")

    # Sort the dataframe by counts and print the top 10 with count > 0
    merged_df.sort_values(by=f'{condition}_{sample_name}_Count', ascending=False, inplace=True)
    print(f"{merged_df[merged_df[f'{condition}_{sample_name}_Count'] > 0].head(10)}\n")


def main():

    samples = get_samples(args.dirs, args.pattern)
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            sample_name = Path(sample).resolve().name
            seg_img_path = Path(sample).resolve() / args.seg_dir / f"{sample_name}_{args.seg_dir}.nii.gz"
            atlas_path = Path(sample).resolve() / args.atlas
            count_cells_in_regions(sample, seg_img_path, atlas_path, args.connect, args.condition)
            progress.update(task_id, advance=1)

    
if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()