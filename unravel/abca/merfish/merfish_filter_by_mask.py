#!/usr/bin/env python3

"""
Use ``abca_merfish_filter_by_mask`` or ``mf_filter_mask``  from UNRAVEL to filter MERFISH cell metadata using a mask image in MERFISH-CCF space.

Prereqs:
    - Use CCF30_to_MERFISH.py to warp the mask image to MERFISH-CCF space

Steps:
    - 1) Binarize the mask image
    - 2) Determine the bounding box of the mask image and filter the cell metadata by the bounding box
    - 3) Loop through each cell and filter out cells whose reconstructed coordinates fall are external to the mask
    - 4) Save the filtered cell metadata to a new CSV file

Next steps:
    - Use the filtered cell metadata to examine cell type prevalence or gene expression
    - For looking at gene expression, load the filtered cell metadata and join it with the expression data for the gene(s) of interest

Usage:
------
    abca_merfish_filter_by_mask -b path/to/root_dir -i mask.nii.gz [-o path/cells_filtered_by_cluster.csv] [-v]
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

import unravel.abca.merfish.merfish as mf
from unravel.cluster_stats.validation import cluster_bbox
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times
from unravel.core.img_io import load_nii


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/mask.nii.gz', required=True, action=SM)
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='path/MERFISH_cells_filtered_by_mask.csv.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

@print_func_name_args_times()
def check_cells_in_mask(cell_df_bbox_filter, mask_img, xy_res, z_res):
    """
    Determines whether each cell is within the mask using a 3D image representation.

    This function converts cell coordinates to voxel indices and stores them in a dictionary, 
    allowing multiple cells per voxel. The function then filters out cells that do not belong 
    to the mask by checking if the voxel indices are present in the mask image.

    Parameters
    ----------
    cell_df_bbox_filter : pd.DataFrame
        DataFrame containing filtered cell metadata, including reconstructed coordinates.
    mask_image : np.ndarray
        A 3D binary NumPy array 
    xy_res : float
        Resolution of the x-y plane in microns (µm).
    z_res : float
        Resolution of the z-plane in microns (µm).

    Returns
    -------
    pd.DataFrame
        A filtered DataFrame containing only the cells that fall within the mask.
    """
    # Convert resolution to mm
    xy_res_mm = xy_res / 1000
    z_res_mm = z_res / 1000

    # Get the shape of the mask image
    x_size, y_size, z_size = mask_img.shape

    # Convert cell coordinates to voxel indices
    cell_df_bbox_filter['x_voxel'] = (cell_df_bbox_filter['x_reconstructed'] / xy_res_mm).astype(int)
    cell_df_bbox_filter['y_voxel'] = (cell_df_bbox_filter['y_reconstructed'] / xy_res_mm).astype(int)
    cell_df_bbox_filter['z_voxel'] = (cell_df_bbox_filter['z_reconstructed'] / z_res_mm).astype(int)

    # Filter out cells that are outside the bounds of the mask image
    in_bounds = (
        (cell_df_bbox_filter['x_voxel'] >= 0) & (cell_df_bbox_filter['x_voxel'] < x_size) &
        (cell_df_bbox_filter['y_voxel'] >= 0) & (cell_df_bbox_filter['y_voxel'] < y_size) &
        (cell_df_bbox_filter['z_voxel'] >= 0) & (cell_df_bbox_filter['z_voxel'] < z_size)
    )
    cell_df_bbox_filter = cell_df_bbox_filter[in_bounds]

    # Create a dictionary to store cell labels per voxel
    cell_dict = {}
    for _, row in cell_df_bbox_filter.iterrows():  # row has the cell's metadata, such as cell label and voxel coordinates 
        voxel_coords = (row['x_voxel'], row['y_voxel'], row['z_voxel'])  # Get the voxel coordinates for the cell
        if voxel_coords not in cell_dict:  # Check if the voxel is already in the dictionary
            cell_dict[voxel_coords] = []  # Initialize the list (value) for the voxel (key). This list will store all cell labels that fall into the same voxel.
        cell_dict[voxel_coords].append(row.name)  # Append the cell_label to the list of cells inside the voxel.

    # Filter only voxels that are inside the mask
    retained_cells = []  # This will store cell labels that belong to voxels inside the mask.
    for (x, y, z), cell_labels in cell_dict.items():
        if mask_img[x, y, z] > 0:  # Check if the voxel is part of the mask
            retained_cells.extend(cell_labels)  # Add the cell labels to the retained_cells lists

    # Filter the original DataFrame based on retained cell labels (index)
    cell_df_final = cell_df_bbox_filter.loc[cell_df_bbox_filter.index.intersection(retained_cells)].copy()

    return cell_df_final


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the mask image
    mask_img = load_nii(args.input)
    
    # These are the resolutions for MERFISH-CCF space
    xy_res = 10
    z_res = 200
    xy_res_mm = xy_res / 1000
    z_res_mm = z_res / 1000
    
    # Binarize
    mask_img[mask_img > 0] = 1

    # Get the bounding box of the mask
    _, xmin, xmax, ymin, ymax, zmin, zmax = cluster_bbox(1, mask_img)

    # Load the cell metadata
    download_base = Path(args.base)

    # Load the cell metadata
    cell_df = mf.load_cell_metadata(download_base)

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = mf.join_reconstructed_coords(cell_df, download_base)

    # Add the classification levels and the corresponding color.
    cell_df_joined = mf.join_cluster_details(cell_df_joined, download_base)

    # Add the cluster colors
    cell_df_joined = mf.join_cluster_colors(cell_df_joined, download_base)
    
    # Add the parcellation annotation
    cell_df_joined = mf.join_parcellation_annotation(cell_df_joined, download_base)

    # Add the parcellation color
    cell_df_joined = mf.join_parcellation_color(cell_df_joined, download_base)

    if args.verbose:
        print(f'\n{cell_df_joined=}\n')

    # Convert the bounding box to float
    xmin, xmax, ymin, ymax, zmin, zmax = map(float, [xmin, xmax, ymin, ymax, zmin, zmax])

    # The bbox needs to be converted to the same units as the reconstructed coordinates, which are in mm
    # The bounding box is in voxel units, so we need to convert it to mm using the voxel size
    xmin_mm = xmin * xy_res_mm
    xmax_mm = xmax * xy_res_mm
    ymin_mm = ymin * xy_res_mm
    ymax_mm = ymax * xy_res_mm
    zmin_mm = zmin * z_res_mm
    zmax_mm = zmax * z_res_mm

    # Print the bounding box in mm
    if args.verbose:
        print(f'\nBounding box of the mask in voxel units:\n')
        print(f'{xmin=}')
        print(f'{xmax=}')
        print(f'{ymin=}')
        print(f'{ymax=}')
        print(f'{zmin=}')
        print(f'{zmax=}\n')

    # Check the min and max values of the reconstructed coordinates
    xmin_reconstructed = cell_df_joined['x_reconstructed'].min()
    xmax_reconstructed = cell_df_joined['x_reconstructed'].max()
    ymin_reconstructed = cell_df_joined['y_reconstructed'].min()
    ymax_reconstructed = cell_df_joined['y_reconstructed'].max()
    zmin_reconstructed = cell_df_joined['z_reconstructed'].min()
    zmax_reconstructed = cell_df_joined['z_reconstructed'].max()

    if args.verbose:
        print(f'\nCell coordinate ranges in mm before filtering by bounding box:\n')
        print(f'{xmax_reconstructed=}')
        print(f'{xmax_reconstructed=}')
        print(f'{ymin_reconstructed=}')
        print(f'{ymax_reconstructed=}')
        print(f'{zmin_reconstructed=}')
        print(f'{zmax_reconstructed=}\n')

    # Filter the cell metadata by the bounding box of the mask using the reconstructed coordinates (x_reconstructed, y_reconstructed, z_reconstructed)
    cell_df_bbox_filter = cell_df_joined[
        (cell_df_joined['x_reconstructed'] >= xmin_mm) &
        (cell_df_joined['x_reconstructed'] <= xmax_mm) &
        (cell_df_joined['y_reconstructed'] >= ymin_mm) &
        (cell_df_joined['y_reconstructed'] <= ymax_mm) &
        (cell_df_joined['z_reconstructed'] >= zmin_mm) &
        (cell_df_joined['z_reconstructed'] <= zmax_mm)
    ]

    # Check the min and max values of the reconstructed coordinates
    xmin_reconstructed = cell_df_bbox_filter['x_reconstructed'].min()
    xmax_reconstructed = cell_df_bbox_filter['x_reconstructed'].max()
    ymin_reconstructed = cell_df_bbox_filter['y_reconstructed'].min()
    ymax_reconstructed = cell_df_bbox_filter['y_reconstructed'].max()
    zmin_reconstructed = cell_df_bbox_filter['z_reconstructed'].min()
    zmax_reconstructed = cell_df_bbox_filter['z_reconstructed'].max()

    if args.verbose:
        print(f'\nCell coordinate ranges in mm after filtering by bounding box:')
        print(f'{xmin_reconstructed=}')
        print(f'{xmax_reconstructed=}')
        print(f'{ymin_reconstructed=}')
        print(f'{ymax_reconstructed=}')
        print(f'{zmin_reconstructed=}')
        print(f'{zmax_reconstructed=}\n')

        print(f'\n{cell_df_bbox_filter=}\n')

    # Loop through each cell and check if it is within the mask
    cell_df_filtered = check_cells_in_mask(cell_df_bbox_filter, mask_img, xy_res=10, z_res=200)

    # Save the filtered cell metadata to a new CSV file
    if args.output:
        output_path = Path(args.output)
        cell_df_filtered.to_csv(output_path)
        print(f"\nFiltered data saved to: {output_path}\n")
    else:
        output_path = Path("MERFISH_cells_filtered_by_mask.csv")
        cell_df_filtered.to_csv(output_path)
        print(f"\nFiltered data saved to: {output_path}\n")
           
    verbose_end_msg()

if __name__ == '__main__':
    main()