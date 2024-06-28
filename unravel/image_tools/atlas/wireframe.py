#!/usr/bin/env python3

"""
Use ``atlas_wireframe`` from UNRAVEL to generate a thin wireframe image from an atlas NIfTI file.

Usage: 
------
    atlas_wireframe -i path.atlas.nii.gz 

Outlines are generated outside the regions and not inside smaller regions. 
For regions at the surface of the brain, the outlines are internalized.

Outputs: 
    - path/atlas_img_W.nii.gz # Wireframe image
    - path/atlas_img_W_IDs.nii.gz # Wireframe image with region IDs
"""

import argparse
import nibabel as nib
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from rich.traceback import install
from scipy.ndimage import binary_dilation, binary_erosion

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a thin wireframe image from an atlas NIfTI file.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/atlas_img.nii.gz', required=True, action=SM)
    parser.add_argument('-wo', '--wire_output', help='Wireframe image output path. Default: path/atlas_img_W.nii.gz', action=SM)
    parser.add_argument('-id', '--id_output', help='Wireframe image with atlas IDs output path. Default: path/atlas_img_W_IDs.nii.gz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def process_intensity(args):
    """
    Process a single intensity: generate its binary mask, dilate, and find boundaries.

    Args:
        args (tuple): A tuple containing the ndarray and the intensity value.

    Returns a tuple with:
        binary_mask (np.ndarray): A binary mask for the given intensity.
        boundary (np.ndarray): A binary boundary mask for the given intensity
    """
    atlas_ndarray, intensity = args
    if intensity == 0:  # Skip background
        # Return an empty mask and boundary
        return np.zeros(atlas_ndarray.shape, dtype=bool), np.zeros(atlas_ndarray.shape, dtype=bool)
    
    binary_mask = atlas_ndarray == intensity # Create a binary mask for the current region
    dilated = binary_dilation(binary_mask) # Dilate the mask
    boundary = dilated != binary_mask # Outline the region (with the line outside the region)
    return binary_mask, boundary

def generate_wireframe(atlas_ndarray, unique_intensities):
    """Generate a wireframe image of an atlas NIfTI file where outlines are outside the regions and not inside smaller regions.
    
    Args:
        atlas_ndarray (np.ndarray): A 3D numpy array of an atlas NIfTI file.
        unique_intensities (np.ndarray): A list of unique intensity values in the atlas ndarray (sorted from smallest to largest regions)

    Returns:
        wireframe_image (np.ndarray): A binary wireframe image (1 = wireframe, 0 = background; uint8)
        wireframe_image_IDs (np.ndarray): A wireframe image with region IDs (uint16)
    """
    
    # Process intensities and boundaries with parallel execution
    with ThreadPoolExecutor() as executor:
        args = [(atlas_ndarray, intensity) for intensity in unique_intensities]
        results = list(executor.map(process_intensity, args)) # List of (binary_mask, boundary) tuples

    wireframe = np.zeros(atlas_ndarray.shape, dtype=bool) # Initialize empty wireframe
    processed_regions_mask = np.zeros(atlas_ndarray.shape, dtype=bool) # Initialize empty mask

    for binary_mask, boundary in results:
        # Add binary mask to the processed regions mask
        processed_regions_mask = np.logical_or(processed_regions_mask, binary_mask)

        # Add the boundary in areas outside of the processed regions mask (excludes boundaries inside smaller regions)
        wireframe = np.logical_or(wireframe, np.logical_and(boundary, np.logical_not(processed_regions_mask)))

    # Internalize outlines at the surfaces of the brain
    brain_mask = atlas_ndarray > 0
    brain_mask_eroded = binary_erosion(brain_mask)
    brain_outline = brain_mask_eroded != brain_mask
    wireframe = wireframe * brain_mask # Zero out the wireframe outside the brain
    wireframe = np.logical_or(wireframe, brain_outline) # Add the brain outline to the wireframe

    # Convert boolean wireframe to binary image (1 = wireframe, 0 = background)
    wireframe_img = wireframe.astype(np.uint16) 

    # Add in Allen brain atlas region IDs (useful for coloring w/ a LUT)
    wireframe_img_IDs = wireframe_img * atlas_ndarray 
    return wireframe_img.astype(np.uint8), wireframe_img_IDs.astype(np.uint16)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the NIfTI file
    atlas_nii = nib.load(args.input)
    atlas_ndarray = atlas_nii.get_fdata(dtype=np.float32)

    # Generate a binary mask for each unique intensity value
    unique_intensities, voxel_counts = np.unique(atlas_ndarray, return_counts=True)

    # Convert to int
    unique_intensities = np.array([int(i) for i in unique_intensities])

    # Create df with unique intensities and counts
    df = pd.DataFrame({'intensity': unique_intensities, 'voxel_count': voxel_counts})
    df = df.sort_values('voxel_count', ascending=True)

    # Sort the unique_intensities list based on the size of their corresponding regions (smallest to largest)
    unique_intensities = df['intensity'].values

    # Generate the wireframe image
    wireframe_img, wireframe_img_IDs = generate_wireframe(atlas_ndarray, unique_intensities)

    # Save the binary wireframe image
    if args.wire_output:
        wire_output = args.wire_output
    else:
        wire_output = str(args.input).replace('.nii.gz', '_W.nii.gz')
    nib.save(nib.Nifti1Image(wireframe_img, atlas_nii.affine, atlas_nii.header), wire_output)

    # Save the wireframe image with region IDs
    if args.id_output:
        id_output = args.id_output
    else:
        id_output = str(args.input).replace('.nii.gz', '_W_IDs.nii.gz')
    nib.save(nib.Nifti1Image(wireframe_img_IDs, atlas_nii.affine, atlas_nii.header), id_output)

    verbose_end_msg()


if __name__ == '__main__':
    main()