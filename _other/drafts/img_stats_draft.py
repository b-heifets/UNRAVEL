#!/usr/bin/env python3

import argparse
import numpy as np
import nibabel as nib
from rich import print
from rich.traceback import install

def parse_args():
    parser = argparse.ArgumentParser(description="Calculate the number of non-zero voxels and the sum of values for all non-zero voxels in a NIfTI image.")
    parser.add_argument('-i', '--input', help="Path to the input NIfTI image.", required=True)
    return parser.parse_args()

def calculate_non_zero_voxels(img_path):
    """
    Calculate the number of non-zero voxels and the sum of values for all non-zero voxels in a 3D image.

    Parameters:
    -----------
    img_path : str or Path
        Path to the input NIfTI image.

    Returns:
    --------
    num_non_zero_voxels : int
        The number of non-zero voxels in the image.

    sum_non_zero_voxels : float
        The sum of values for all non-zero voxels in the image.
    """
    # Load the image
    img = nib.load(img_path)
    img_data = img.get_fdata()

    # Calculate the number of non-zero voxels
    num_non_zero_voxels = np.count_nonzero(img_data)

    # Calculate the sum of values for all non-zero voxels
    sum_non_zero_voxels = np.sum(img_data[img_data > 0])

    return num_non_zero_voxels, sum_non_zero_voxels

def main():
    install()  # This sets up better tracebacks in the terminal
    args = parse_args()

    # Calculate non-zero voxel statistics
    num_non_zero_voxels, sum_non_zero_voxels = calculate_non_zero_voxels(args.input)

    # Print the results
    print(f"\nNumber of non-zero voxels: {num_non_zero_voxels}")
    print(f"Sum of values for all non-zero voxels: {sum_non_zero_voxels}\n")

if __name__ == "__main__":
    main()
