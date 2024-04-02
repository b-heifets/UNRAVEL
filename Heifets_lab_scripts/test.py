#!/usr/bin/env python3

import sys
import nibabel as nib
import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion

def generate_wireframe(nii_path):
    # Load the NIfTI file
    img = nib.load(nii_path)
    data = img.get_fdata()
    
    # Generate a binary mask for each unique intensity value
    unique_intensities = np.unique(data)

    # Convert to int
    unique_intensities = np.array([int(i) for i in unique_intensities])

    print(f'\n{unique_intensities=}\n')

    wireframe = np.zeros(data.shape, dtype=np.uint8)  # Initialize empty wireframe
    
    for intensity in unique_intensities:
        print(f'{intensity=}')
        if intensity == 0:  # Skip background
            continue
        
        # Create a binary mask for the current region
        binary_mask = data == intensity
        
        # Dilate and then erode the mask to get the boundary (outline)
        dilated = binary_dilation(binary_mask)
        eroded = binary_erosion(binary_mask)
        boundary = dilated != eroded
        
        # Add the boundary to the wireframe
        wireframe = np.logical_or(wireframe, boundary)
    
    # Convert boolean wireframe to binary image (1 = wireframe, 0 = background)
    wireframe_image = wireframe.astype(np.uint8)

    # Save or display the wireframe image as needed
    nib.save(nib.Nifti1Image(wireframe_image, img.affine, img.header), str(nii_path).replace('.nii.gz', 'W.nii.gz'))
    
    return wireframe_image

nii_path = sys.argv[1]
wireframe_image = generate_wireframe(nii_path)

# Here you can save or visualize `wireframe_image` as needed.