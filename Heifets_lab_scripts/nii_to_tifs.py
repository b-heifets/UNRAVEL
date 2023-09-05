#!/usr/bin/env python3

import argparse
import os
import nibabel as nib
import numpy as np
import tifffile as tif
from unravel_utils import print_cmd

def parse_args():
    parser = argparse.ArgumentParser(description='''Converts image.nii.gz to tif series''')
    parser.add_argument('-i', '--input', help='image.nii.gz', metavar='')
    parser.add_argument('-o', '--output_dir', help='Name of output folder', metavar='')
    return parser.parse_args()

def nii_to_tifs(nii_path, output_dir):
    # Load the NIfTI file
    nii_image = nib.load(nii_path)
    data = nii_image.get_fdata()

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
    print_cmd()
    nii_to_tifs(args.input, args.output_dir)

if __name__ == '__main__':
    main()

#Daniel Rijsketic 08/25/23 (Heifets lab) 
