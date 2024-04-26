#!/usr/bin/env python3

import argparse
import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Averages NIfTI images in the current directory or specified by user.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--inputs', help='Input file(s) or pattern(s) to process. Default is "*.nii.gz".',  nargs='*', default=['*.nii.gz'], action=SM)
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Resolve file patterns to actual file paths
    all_files = []
    for pattern in args.inputs:
        all_files.extend(Path().glob(pattern))

    print(f'\nAveraging: {str(all_files)}\n')

    if not all_files:
        print("No NIfTI files found. Exiting.")
        return

    # Initialize sum array and affine matrix
    sum_image = None
    affine = None

    # Process each file
    for file_path in all_files:
        nii = nib.load(str(file_path))
        if sum_image is None:
            sum_image = np.asanyarray(nii.dataobj, dtype=np.float64).squeeze()  # Use float64 to avoid overflow
            affine = nii.affine
            header = nii.header
            data_type = nii.header.get_data_dtype()
        else:
            sum_image += np.asanyarray(nii.dataobj, dtype=np.float64).squeeze()
    

    # Calculate the average
    average_image = sum_image / len(all_files)

    # Save the averaged image
    averaged_nii = nib.Nifti1Image(average_image, affine, header)
    averaged_nii.set_data_dtype(data_type)
    nib.save(averaged_nii, "avg.nii.gz")
    print("Saved averaged image to ave.nii.gz\n")


if __name__ == '__main__': 
    install()
    main()