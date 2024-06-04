#!/usr/bin/env python3

import sys
import nibabel as nib
import numpy as np


def find_max_intensity(file_path):
    """Find the maximum intensity value in the NIfTI image file."""
    # Load the .nii.gz file
    nii_img = nib.load(file_path)
    
    # Get the data from the file
    data = nii_img.get_fdata(dtype=np.float32)
    
    # Find the maximum intensity value in the data
    max_intensity = int(data.max())
    
    return max_intensity


if __name__ == '__main__':
    file_path = sys.argv[1]
    max_intensity = find_max_intensity(file_path)
    print(max_intensity)