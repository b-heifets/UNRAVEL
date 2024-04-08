#!/usr/bin/env python3

import sys
import nibabel as nib
import numpy as np

file_path = sys.argv[1]

# Load the .nii.gz file
nii_img = nib.load(file_path)

# Get the data from the file
data = nii_img.get_fdata(dtype=np.float32)

# Find the maximum intensity value in the data
max_intensity = int(data.max())

print(max_intensity)
