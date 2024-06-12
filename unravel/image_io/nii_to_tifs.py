#!/usr/bin/env python3

"""
Converts image.nii.gz to tif series in output_dir.
"""

import argparse
import os
import nibabel as nib
import numpy as np
import tifffile as tif

from unravel.core.argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='image.nii.gz', action=SM)
    parser.add_argument('-o', '--output_dir', help='Name of output folder', action=SM)
    parser.epilog = __doc__
    return parser.parse_args()

def nii_to_tifs(nii_path, output_dir):
    # Load the NIfTI file
    nii_image = nib.load(nii_path)
    data = nii_image.get_fdata(dtype=np.float32)

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Iterate through the slices of the image and save each as a .tif
    for i in range(data.shape[2]):
        slice_ = data[:, :, i]
        slice_ = np.rot90(slice_, 1)  # '1' indicates one 90-degree rotation counter-clockwise
        slice_ = np.flipud(slice_) # Flip vertically
        tif.imwrite(os.path.join(output_dir, f'slice_{i:04d}.tif'), slice_) #not opening in FIJI as one stack

def main():
    args = parse_args()
    
    nii_to_tifs(args.input, args.output_dir)

if __name__ == '__main__':
    main()

#Daniel Rijsketic 08/25/23 (Heifets lab) 
