#!/usr/bin/env python3

import argparse
import cc3d
import numpy as np
import pandas as pd
from unravel_config import Configuration
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Perform regional cell counting')
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process.', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='path/img.nii.gz', metavar='')
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz', metavar='')
    parser.add_argument('-c', '--connectivity', help='6, 18, or 26. Default: 6', type=int, default=6, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Run from experiment folder containing sample?? folders."
    return parser.parse_args()


def get_region_id_with_progress(atlas, x, y, z, progress, task_id):
    """"Get the ndarray atlas region intensity at the given coordinates"""
    progress.update(task_id, advance=1)
    return atlas[int(x), int(y), int(z)]

@print_func_name_args_times()
def count_cells_in_regions(img_path, atlas_path, connectivity):
    """Count the number of cells in each region based on atlas region intensities"""

    img = load_3D_img(img_path)
    atlas = load_3D_img(atlas_path)

    # If the data is big-endian, convert it to little-endian
    if img.dtype.byteorder == '>':
        img = img.byteswap().newbyteorder()
    img = img.astype(np.uint8)

    connectivity = 6
    labels_out, n = cc3d.connected_components(img, connectivity=connectivity, out_dtype=np.uint32, return_N=True)

    print(f"\n    Total cell count: {n+1}\n")

    # Get cell coordinates from the labeled image
    print("    Getting cell coordinates")
    stats = cc3d.statistics(labels_out)

    # Convert the dictionary to a dataframe
    print("    Converting to dataframe")
    centroids = stats['centroids']
    centroids_df = pd.DataFrame(centroids, columns=['x', 'y', 'z'])

    # Get the region ID for each cell
    progress, task_id = initialize_progress_bar(len(centroids_df), "    [red]Getting region ID for each cell")
    with Live(progress):
        centroids_df['region_ID'] = centroids_df.apply(lambda row: get_region_id_with_progress(
            atlas, row['x'], row['y'], row['z'], progress, task_id
        ), axis=1)        

    # Count how many centroids are in each region
    print("    Counting cells in each region")
    region_counts = centroids_df['region_ID'].value_counts()

    return region_counts


def main():    
    region_counts = count_cells_in_regions(args.input, args.atlas, args.connectivity)

    # Save the region counts as a csv file
    output_path = Path(args.input).parent / "region_cell_counts.csv"
    region_counts.to_csv(output_path, header=True)
    print(region_counts)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()