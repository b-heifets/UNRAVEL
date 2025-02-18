#!/usr/bin/env python3

"""
Filter cells in MERFISH-CCF space using a mask and process MERFISH data.

This script filters cells based on their reconstructed coordinates in MERFISH-CCF space, removing cells that fall outside a specified mask. It integrates the filtering with the generation of `exp_df` and allows optional export of filtered data or the generation of updated 3D images.

Usage:
------
    ./filter_cells_by_mask.py -b path/to/base_dir -g gene -mas path/to/mask.nii.gz [-o path/to/output.nii.gz] [-v]
"""

import anndata
import numpy as np
import pandas as pd
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

import merfish as m
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


### Tentative plan: for each metadata cell, check if the reconstructed coordinates fall within the mask. If so, keep the cell. Otherwise, discard it.

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-b', '--base', help='Path to the root directory of the Allen Brain Cell Atlas data', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to process.', required=True, action=SM)
    reqs.add_argument('-mas', '--mask', help='Path to the mask in MERFISH-CCF space.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Output path for the filtered 3D .nii.gz image. Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def filter_cells_by_mask(cell_df_joined, mask_path):
    """
    Filter Allen Brain Cell Atlas MERFISH cells based on whether their reconstructed coordinates fall inside the mask.

    Parameters:
    -----------
    cell_df_joined : pd.DataFrame
        DataFrame containing cell metadata with reconstructed coordinates.

    mask_path : str
        Path to the mask NIfTI file.

    Returns:
    --------
    filtered_df : pd.DataFrame
        Filtered DataFrame containing only cells inside the mask.
    """

    # For cells within

    print(f"Loading mask: {mask_path}")
    mask_img = nib.load(mask_path)
    mask_data = mask_img.get_fdata()
    mask_affine = mask_img.affine

    # Convert reconstructed coordinates to voxel indices
    coords = cell_df_joined[['x_reconstructed', 'y_reconstructed', 'z_reconstructed']].values
    voxel_indices = nib.affines.apply_affine(np.linalg.inv(mask_affine), coords).astype(int)

    # Ensure indices are within bounds of the mask
    valid_mask = (
        (voxel_indices[:, 0] >= 0) & (voxel_indices[:, 0] < mask_data.shape[0]) &
        (voxel_indices[:, 1] >= 0) & (voxel_indices[:, 1] < mask_data.shape[1]) &
        (voxel_indices[:, 2] >= 0) & (voxel_indices[:, 2] < mask_data.shape[2])
    )
    voxel_indices = voxel_indices[valid_mask]

    # Filter cells based on the mask
    mask_values = mask_data[voxel_indices[:, 0], voxel_indices[:, 1], voxel_indices[:, 2]]
    inside_mask = mask_values > 0  # Assuming non-zero mask values indicate valid regions

    filtered_df = cell_df_joined.iloc[valid_mask][inside_mask]
    return filtered_df




@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    download_base = Path(args.base)

    # Load the cell metadata
    cell_df = m.load_cell_metadata(download_base)

    # Add the reconstructed coordinates to the cell metadata
    cell_df_joined = m.join_reconstructed_coords(cell_df, download_base)

    # Add the classification levels and the corresponding color.
    cell_df_joined = m.join_cluster_details(cell_df_joined, download_base)

    # Add the cluster colors
    cell_df_joined = m.join_cluster_colors(cell_df_joined, download_base)
    
    # Add the parcellation annotation
    cell_df_joined = m.join_parcellation_annotation(cell_df_joined, download_base)

    # Add the parcellation color
    cell_df_joined = m.join_parcellation_color(cell_df_joined, download_base)

    # Print the columns and the first row
    print("\nCell metadata columns:")
    print(cell_df_joined.columns)
    print("\nFirst row:")
    print(cell_df_joined.iloc[0])

    # Filter by 'parcellation_substructure' to only include ACB for testing
    cell_df_joined = cell_df_joined[cell_df_joined['parcellation_substructure'] == 'ACB']  # This can be used for region-specific filtering (could allow selection of both column and value(s))

    print("\nCell metadata columns:")
    print(cell_df_joined.columns)
    print("\nFirst row:")
    print(cell_df_joined.iloc[0])

    print(cell_df_joined)

    print("\nUnique parcellation substructures:")
    print(cell_df_joined['parcellation_substructure'].unique())

    

    import sys ; sys.exit()

    # Filter cells by the mask
    filtered_cells = filter_cells_by_mask(cell_df_joined, args.mask)


    import sys ; sys.exit()

    # Load the expression data for all genes (if the gene is in the dataset) 
    adata = m.load_expression_data(download_base, args.gene)

    # Filter expression data for the specified gene
    asubset, gf = m.filter_expression_data(adata, args.gene)

    # Generate `exp_df` for filtered cells
    exp_df = m.create_expression_dataframe(asubset, gf, filtered_cells)
    print(f"\nFiltered exp_df created with {len(exp_df)} cells.")

    if args.output:
        # Create a 3D image from the filtered data
        print("\nGenerating 3D image from filtered data...")
        z_positions = np.sort(filtered_cells['z_reconstructed'].unique())
        img = np.zeros((1100, 1100, 76))

        for z in z_positions:
            img = m.add_merfish_slice_to_3d_img(z, filtered_cells, asubset, gf, args.gene, img)

        # Save the 3D image
        ref_nii = nib.load(args.mask)  # Use the mask for affine/header info
        nii_img = nib.Nifti1Image(img, affine=ref_nii.affine, header=ref_nii.header)
        nib.save(nii_img, args.output)
        print(f"\nFiltered 3D image saved to: {args.output}\n")

    verbose_end_msg()


if __name__ == '__main__':
    main()
