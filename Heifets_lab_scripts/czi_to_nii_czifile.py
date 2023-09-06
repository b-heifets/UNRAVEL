#!/usr/bin/env python3

import argparse
import czifile
import os
import nibabel as nib
import numpy as np
from glob import glob
from glob import glob
from pathlib import Path
from rich import print
from scipy import ndimage
import unravel_utils as unrvl

def parse_args():
    parser = argparse.ArgumentParser(description='Load channel of *.czi, downsample/resample, reorient, and save as .nii.gz')
    parser.add_argument('-o', '--output', help='img.nii.gz', default="clar_res0.05.nii.gz", metavar='')
    parser.add_argument('-c', '--channel', help='Channel number (0 for 1st channel)', default=0, type=int, metavar='')
    parser.add_argument('-d', '--ds_factor', help='Downsampling factor', default=3, type=int,  metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns', default=3.5232, type=float, metavar='') 
    parser.add_argument('-z', '--z_res', help='x/y voxel size in microns', default=6, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution (microns)', default=50, type=int, metavar='')
    return parser.parse_args()

args = parse_args() 



def get_czi(sample_dirs): 
    '''
    Returns the path to the first .czi file in the sample folder
    '''
    czi_files = glob(f"{sample_dirs}/*.czi")
    
    if not czi_files:
        print(f"  [red]No .czi found in {sample_dirs}[\]")
        return None

    return os.path.join(sample_dirs, czi_files[0])

def load_channel_from_czi(czi_image, channel): 
    '''
    Loads the specified channel of the .czi file as a numpy array
    '''
    with czifile.CziFile(czi_image) as czi:
        czi_array = czi.asarray()
        image = czi_array[..., channel, :, :, :, :]
        image = np.squeeze(image)
        image = np.transpose(image, (2, 1, 0))
        return image  

def downsample(image, ds_factor):
    '''
    Quickly downsamples the image by the specified factor:
    Drop voxels via slicing, keeping the middle voxel if the downscale factor is odd
    '''
    if ds_factor > 1:
        start_index = ds_factor // 2 if ds_factor % 2 == 1 else (ds_factor - 1) // 2
        image = image[start_index::ds_factor, start_index::ds_factor, start_index::ds_factor]
    return image

def resample(image, ds_factor, xy_res, z_res, target_resolution):
    '''
    Resamples the image to the specified resolution (in microns)
    '''
    if ds_factor == 1: # If not downsampling, use the original resolution
        # Zoom factors:
        zf_xy = float(xy_res)/float(target_resolution)
        zf_z = float(z_res)/float(target_resolution)
    else:
        # Zoom factors:
        zf_xy = float(xy_res * ds_factor)/float(target_resolution)
        zf_z = float(z_res * ds_factor)/float(target_resolution)
    resampled_img = ndimage.zoom(image, (zf_xy, zf_xy, zf_z), order=1) #order of 0 = NN interpolation, 1 for linear
    return resampled_img

def reorient(image):
    '''
    Reorients the image following MIRACL's convention
    '''
    # reoriented_image = np.rollaxis(image, 0, 3)
    # return reoriented_image

    # Rotate 90 degrees counterclockwise on the x-y plane
    rotated = np.rot90(image, axes=(1, 0))

    # Flip vertically
    reoriented_image = np.flip(rotated, axis=1)

    return reoriented_image

def make_output_nii_dir(sample_dirs):
    '''
    Creates a directory for the output .nii.gz file
    '''
    sample_dirs = Path(sample_dirs)
    output_dir = os.path.join(sample_dirs, "niftis")
    os.makedirs(output_dir, exist_ok=True)

def save_as_nii(sample_dirs, image, output_name, target_resolution):
    '''
    Saves the image as a .nii.gz file
    '''
    # Create new identity matrix
    res = target_resolution / 1000 # convert to mm
    affine = np.eye(4) * res
    affine[3, 3] = 1

    # Save as nii.gz
    nifti = nib.Nifti1Image(image, affine)
    nifti.header.set_data_dtype(np.int16)
    nifti.header.set_zooms([res, res, res])
    output = os.path.join(sample_dirs, "niftis", output_name)
    nib.save(nifti, output)



@unrvl.function_decorator(message='') # Returns paths to sample folders and loops over them, passing each path to main()
def load_czi_downsample_resample_save_nii(sample_dirs, channel, ds_factor, xy_res, z_res, target_resolution, output_name):
    '''
    Loads the specified channel of the .czi file, downsamples/resamples, reorients, and saves as .nii.gz
    '''
    # Load .czi file
    czi_image = get_czi(sample_dirs)
    if not czi_image:
        return  # Exit the function if no .czi file is found
    
    # Load channel of .czi file
    image = load_channel_from_czi(czi_image, channel)
    
    # Downsample
    downsampled_image = downsample(image, ds_factor)

    # Resample
    resampled_image = resample(downsampled_image, ds_factor, xy_res, z_res, target_resolution)

    # Reorient
    reoriented_image = reorient(resampled_image)

    # Make output directory
    make_output_nii_dir(sample_dirs)

    # Save as .nii
    save_as_nii(sample_dirs, reoriented_image, output_name, target_resolution)



@unrvl.main_function_decorator(pattern='sample??') # Adjust sample folder pattern as needed (e.g., 'sample??' for sample01, etc.)
def main(sample_dirs):
    args = parse_args() 

    load_czi_downsample_resample_save_nii(sample_dirs, args.channel, args.ds_factor, args.xy_res, args.z_res, args.res, args.output)



if __name__ == '__main__':
    main()

# Daniel Rijsketic 08/29-31/2023 (Heifets lab)
# Wesley Zhao 08/30/2023 (Heifets lab)

# To do:
# Add option to get voxel size from metadata
# Consider splitting up the load_czi_downsample_resample_save_nii function so that it can be reused for other scripts like the following:
# Create alternate python script for starting from a tif series (e.g., data from UltraII microscope)
# Does voxel_drop_middle already work correctly when xy_res and z_res are different? (e.g., 3.5232 and 6)
# Make the interpolation order for zoom an optional argument

# Notes: for testing:
# cd /SSD3/test/sample_w_czi/
# czi_to_nii.py #voxel drop downsample factor 3 (output renamed with d3)
# czi_to_nii.py -d 1 #just zoom (output renamed with d1)
# output: 
# /SSD3/test/sample_w_czi/sample13/niftis/clar_res0.05.nii.gz
# Either method takes 17 seconds
# Image smoothness similar but not identical. Since it is just as fast to use zoom, we should probably drop voxel drop and add in an optional arg for the interpolation order
# /SSD3/test/sample_w_czi/sample13/niftis/clar_res0.05_sh.nii.gz from 'prep_reg.sh 3.5232 6 488 8' is smoother, so we could try with an order of 2 or 3 with zoom for comparison
