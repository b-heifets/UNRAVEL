#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from scipy.ndimage import binary_dilation, binary_erosion


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a wireframe image from an atlas NIfTI file.')
    parser.add_argument('-i', '--input', help='path/atlas_img.nii.gz', required=True, type=str, metavar='')
    parser.epilog = """wireframe.py -i path.atlas.nii.gz 

Outputs: 
path/atlas_imgW.nii.gz
path/atlas_imgW_IDs.nii.gz
"""
    return parser.parse_args()


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a wireframe image from an atlas NIfTI file.')
    parser.add_argument('-i', '--input', required=True, help='Input NIfTI file path (e.g., path/img.nii.gz)', type=str)
    parser.add_argument('-o', '--output', help='Output NIfTI file base path without extension (default: based on input file)', type=str)
    return parser.parse_args()

def process_intensity(args):
    """
    Process a single intensity: generate its binary mask, dilate, erode, and find boundaries.

    Args:
        args (tuple): A tuple containing the ndarray and the intensity value.

    Returns:
        boundary (np.ndarray): A binary boundary mask for the given intensity.
    """
    atlas_ndarray, intensity = args
    if intensity == 0:  # Skip background
        return np.zeros(atlas_ndarray.shape, dtype=bool) # Return an empty boundary
    
    binary_mask = atlas_ndarray == intensity
    dilated = binary_dilation(binary_mask)
    eroded = binary_erosion(binary_mask)
    boundary = dilated != eroded
    return boundary


def generate_wireframe(atlas_ndarray):
    """Generate a wireframe image from a binary mask stored in a NIfTI file.
    Args:
        nii_path (str): Path to the input NIfTI file.

    Returns:
        wireframe_image (np.ndarray): A binary wireframe image (1 = wireframe, 0 = background; uint8)
        wireframe_image_IDs (np.ndarray): A wireframe image with region IDs (uint16)
    """
    # Generate a binary mask for each unique intensity value
    unique_intensities = np.unique(atlas_ndarray)

    # Convert to int
    unique_intensities = np.array([int(i) for i in unique_intensities])

    # Initialize empty wireframe
    wireframe = np.zeros(atlas_ndarray.shape, dtype=bool)  
    
    # Setup ThreadPoolExecutor
    with ThreadPoolExecutor() as executor:
        args = [(atlas_ndarray, intensity) for intensity in unique_intensities]
        for boundary in executor.map(process_intensity, args):
            wireframe = np.logical_or(wireframe, boundary) # Add the boundary to the wireframe
    
    # Convert boolean wireframe to binary image (1 = wireframe, 0 = background)
    wireframe_img = wireframe.astype(np.uint16) 

    # Add in Allen brain atlas region IDs (useful for coloring w/ a LUT)
    wireframe_img_IDs = wireframe_img * atlas_ndarray

    return wireframe_img.astype(np.uint8), wireframe_img_IDs.astype(np.uint16)


def main():
    args = parse_args()

    # Load the NIfTI file
    atlas_nii = nib.load(args.input)
    atlas_ndarray = atlas_nii.get_fdata()

    # Generate the wireframe image
    wireframe_img, wireframe_img_IDs = generate_wireframe(atlas_ndarray)

    # Save the binary wireframe image
    output = args.output if args.output else str(args.input).replace('.nii.gz', 'W.nii.gz')
    nib.save(nib.Nifti1Image(wireframe_img, atlas_nii.affine, atlas_nii.header), output)

    # Save the wireframe image with region IDs
    output = str(args.input).replace('.nii.gz', 'W_IDs.nii.gz')
    nib.save(nib.Nifti1Image(wireframe_img_IDs, atlas_nii.affine, atlas_nii.header), output)

    
if __name__ == '__main__':
    main()