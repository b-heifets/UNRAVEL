#!/usr/bin/env python3

import anndata
import numpy as np
import pandas as pd
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-r', '--root', help='Path to the root directory of the MERFISH data', required=True, action=SM)
    reqs.add_argument('-g', '--gene', help='Gene to plot.', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Output path for the saved .nii.gz image. Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# Helper function to create expression DataFrame
def create_expression_dataframe(anndata_obj, gene_symbol):
    """
    Extracts expression data for a specific gene by its symbol and returns a DataFrame.
    """
    # Find the corresponding Ensembl ID for the gene symbol
    ens_id = anndata_obj.var[anndata_obj.var['gene_symbol'] == gene_symbol].index
    if len(ens_id) == 0:
        raise ValueError(f"Gene symbol {gene_symbol} not found in dataset.")
    
    # Extract expression data for the gene
    gene_data = anndata_obj[:, ens_id].to_df()
    return gene_data, ens_id[0]  # Return the expression data and Ensembl ID

# Generate a 2D image from points
def points_to_img_sum(points_ndarray, x_size=1100, y_size=1100, pixel_size=10):
    """
    Generates a 2D image slice by summing the expression values of all cells in each pixel.
    
    Parameters:
    -----------
    points_ndarray : np.ndarray
        A 2D ndarray containing the x, y coordinates of cells as well as expression values.
    
    x_size : int, optional
        The size of the image along the x-axis. Default is 1100.

    y_size : int, optional
        The size of the image along the y-axis. Default is 1100.

    pixel_size : int, optional
        The size of each pixel in microns. Default is 10.

    Returns:
    --------
    img : np.ndarray
        A 2D ndarray representing the image slice.
    """
    # Create an empty image of the desired size (1100 x 1100)
    img = np.zeros((y_size, x_size))

    # Swap X and Y coordinates if necessary
    swapped_points_ndarray = points_ndarray[:, [1, 0, 2]]  # Swap X and Y

    # Convert coordinates to pixel indices based on the voxel size
    x_indices = ((swapped_points_ndarray[:, 0]) / (pixel_size / 1000)).astype(int)
    y_indices = ((swapped_points_ndarray[:, 1]) / (pixel_size / 1000)).astype(int)

    # Ensure pixel indices are within bounds of the image
    valid_mask = (x_indices >= 0) & (x_indices < x_size) & (y_indices >= 0) & (y_indices < y_size)
    x_indices = x_indices[valid_mask]
    y_indices = y_indices[valid_mask]
    values = swapped_points_ndarray[:, 2][valid_mask]  # expression values

    # Increment the voxel value for each point's coordinates
    for x, y, value in zip(x_indices, y_indices, values):
        img[y, x] += value

    return img

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    root_dir = Path(args.root)

    # Load the expression data
    expression_path = root_dir / 'expression_matrices/MERFISH-C57BL6J-638850/20230830/C57BL6J-638850-log2.h5ad'
    print(f"\nLoading expression data from {expression_path}\n")
    adata = anndata.read_h5ad(expression_path)

    # Load the metadata
    cell_metadata_path = root_dir / 'metadata/MERFISH-C57BL6J-638850/20231215/views/cell_metadata_with_cluster_annotation.csv'
    reconstructed_coords_path = root_dir / 'metadata/MERFISH-C57BL6J-638850-CCF/20231215/reconstructed_coordinates.csv'

    # Read in metadata files
    print(f"\nLoading metadata from {cell_metadata_path}\n")
    cell_metadata = pd.read_csv(cell_metadata_path)

    print(f"\nLoading reconstructed coordinates from {reconstructed_coords_path}\n")
    reconstructed_coords = pd.read_csv(reconstructed_coords_path, dtype={'cell_label': str})

    # Rename the columns to distinguish CCF coordinates from MERFISH coordinates
    reconstructed_coords.rename(columns={'x': 'x_ccf', 'y': 'y_ccf', 'z': 'z_ccf'}, inplace=True)

    # Join metadata and expression data
    print(f"\nCreating expression DataFrame for gene: {args.gene}\n")
    gene_expression_df, ensembl_id = create_expression_dataframe(adata, args.gene)

    # Reset index to avoid misalignment issues
    full_data = pd.concat([cell_metadata.reset_index(drop=True), 
                           reconstructed_coords.reset_index(drop=True), 
                           gene_expression_df.reset_index(drop=True)], axis=1)

    # Get unique Z coordinates (slices)
    unique_z_values = np.sort(full_data['z_ccf'].unique())
    
    # Constants for padding
    z_min_template = -8.6  # Starting Z value of the template (in mm)
    z_max_template = z_min_template + (75 * 0.2)  # 75 slices, 0.2 mm voxel size in Z direction
    voxel_z_size = 0.2  # Z voxel size in mm (200 microns)

    # Calculate the number of zero slices required to pad at the beginning and end
    pad_start = 5
    pad_end = 17

    # Create an empty 3D image with shape (x, y, z) including padding
    img_3d = np.zeros((1100, 1100, len(unique_z_values) + pad_start + pad_end))

    # Insert zero slices at the start and end (padding)
    z_offset = pad_start
    # Iterate through each z slice and populate the 3D array
    for z_idx, z_value in enumerate(unique_z_values):
        valid_data = full_data[(full_data['z_ccf'] == z_value) & (full_data[ensembl_id].notna())]
        
        # Make df with only x_ccf, y_ccf, and expression values
        valid_data = valid_data[['x_ccf', 'y_ccf', ensembl_id]]
        
        # Extract the ndarray of coordinates from the DataFrame
        points_ndarray = valid_data[['x_ccf', 'y_ccf', ensembl_id]].values
        
        # Generate the image slice
        img_slice = points_to_img_sum(points_ndarray, x_size=1100, y_size=1100, pixel_size=10)
        
        # Insert the slice into the 3D image at the correct position
        img_3d[:, :, z_idx + z_offset] = img_slice

    # Define affine matrix for saving the NIfTI image
    affine = np.array([
        [0.01, 0, 0, -5.4765],
        [0, 0, 0.2, -8.6],
        [0, -0.01, 0, 6.4357],
        [0, 0, 0, 1]
    ])

    # Save the image as a .nii.gz file
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = root_dir / f"{args.gene}_3D_expression.nii.gz"
        
    nii_img = nib.Nifti1Image(img_3d, affine=affine)
    nib.save(nii_img, str(output_path))
    print(f"\nSaved 3D image to {output_path}\n")

    verbose_end_msg()


if __name__ == '__main__':
    main()
