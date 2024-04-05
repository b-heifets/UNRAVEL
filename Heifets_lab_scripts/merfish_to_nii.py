#!/usr/bin/env python3

import argparse
import pandas as pd
import numpy as np
import anndata
import nibabel as nib
from abc_atlas_access.abc_atlas_cache.abc_project_cache import AbcProjectCache
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description='Visualize MERFISH data in the Allen Brain Atlas', formatter_class=SuppressMetavar)
    parser.add_argument('-b', '--base_dir', help='path/base_dir (abc_download_root)', required=True, action=SM)
    parser.add_argument('-d', '--dir', help='Directory name in the cache', default='MERFISH-C57BL6J-638850-CCF', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


def main():
    # Update the base download directory to your local path
    download_base = Path(args.base_dir)
    abc_cache = AbcProjectCache.from_s3_cache(download_base)

    # Load cell metadata with reconstructed coordinates
    cell_metadata = abc_cache.get_metadata_dataframe(directory='MERFISH-C57BL6J-638850', file_name='cell_metadata_with_cluster_annotation')

    # Assuming 'HTR2a_expression' is a column in your cell metadata indicating the expression level of HTR2a
    # For simplicity, we're treating any positive value as expression here
    htr2a_cells = cell_metadata[cell_metadata['HTR2a_expression'] > 0]

    # Dimensions based on CCFv3 space - you might need to adjust these based on your data
    dim_x, dim_y, dim_z = 1320, 800, 114  # Example dimensions

    # Create a 3D numpy array to store expression data
    expression_map = np.zeros((dim_z, dim_y, dim_x))

    # Populate the 3D array with HTR2a expression levels
    for index, row in htr2a_cells.iterrows():
        x, y, z = int(row['x_reconstructed']), int(row['y_reconstructed']), int(row['z_reconstructed'])
        expression_map[z, y, x] = row['HTR2a_expression']

    # Convert the numpy array to a NIfTI image
    nifti_img = nib.Nifti1Image(expression_map, affine=np.eye(4))

    # Save the NIfTI image to disk
    nib.save(nifti_img, 'HTR2a_expression_map.nii.gz')

    print("3D map of HTR2a expression saved as 'HTR2a_expression_map.nii.gz'.")

if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()