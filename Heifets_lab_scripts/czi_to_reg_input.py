#!/usr/bin/env python3

import argparse
import os
import nibabel as nib
import numpy as np
import unravel_utils as unrvl
from aicspylibczi import CziFile
from glob import glob
from metadata import get_metadata_from_czi
from pathlib import Path
from rich import print
from scipy import ndimage

def parse_args():
    parser = argparse.ArgumentParser(description='Load channel of *.czi, resample, reorient, and save as .nii.gz')
    # parser.add_argument('-i', '--input', help='Path to input .czi file (Default: auto-detect in sample directory)', default=None, metavar='')
    parser.add_argument('-o', '--output', help='img.nii.gz (default: clar_res0.05.nii.gz)', default="clar_res0.05.nii.gz", metavar='')
    parser.add_argument('-c', '--channel', help='Channel number (Default: 0 for 1st channel)', default=0, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='') 
    parser.add_argument('-z', '--z_res', help='z voxel size in microns', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution (microns)', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    return parser.parse_args()

args = parse_args() 

def get_czi(sample_dirs, input_path): 
    '''
    Returns the path to the .czi file. If input_path is provided, it takes precedence. 
    Otherwise, it looks for the first .czi file in the sample folder.
    '''
    if input_path is not None:
        return input_path

    czi_files = glob(f"{sample_dirs}/*.czi")
    
    if not czi_files:
        print(f"  [red]No .czi found in {sample_dirs}[\]")
        return None

    return os.path.join(sample_dirs, czi_files[0])

def load_channel_from_czi(czi_image, channel): 
    '''
    Loads the specified channel of the .czi file as a numpy array
    '''
    with CziFile(czi_image) as czi:
        image = czi.read_image(C=channel)
        image = np.squeeze(image)
        image = np.transpose(image, (2, 1, 0))
    return image  

def resample(image, xy_res, z_res, target_resolution, zoom_order):
    '''
    Resamples the image to the specified resolution (in microns)
    '''
    # Zoom factors:
    zf_xy = float(xy_res)/float(target_resolution)
    zf_z = float(z_res)/float(target_resolution)

    resampled_img = ndimage.zoom(image, (zf_xy, zf_xy, zf_z), order=zoom_order) #order of 0 = NN interpolation, 1 for linear
    return resampled_img

def reorient(image):
    '''
    Reorients the image following MIRACL's convention in tiff to nii conversion
    '''
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
def load_czi_resample_save_nii(sample_dirs, channel, xy_res, z_res, target_resolution, zoom_order, output_name):
    '''
    Loads the specified channel of the .czi file, resamples, reorients, and saves as .nii.gz
    '''
    # Load .czi file
    czi_image = get_czi(sample_dirs, args.input)
    if not czi_image:
        return  # Exit the function if no .czi file is found
    
    # If xy_res and z_res are default, then fetch from metadata
    if xy_res is None or z_res is None:
        _, _, _, x_res_metadata, _, z_res_metadata = get_metadata_from_czi(czi_image)
        xy_res = xy_res if xy_res is not None else x_res_metadata
        z_res = z_res if z_res is not None else z_res_metadata
    
    # Load channel of .czi file
    image = load_channel_from_czi(czi_image, channel)

    # Resample
    resampled_image = resample(image, xy_res, z_res, target_resolution, zoom_order)

    # Reorient
    reoriented_image = reorient(resampled_image)

    # Make output directory
    make_output_nii_dir(sample_dirs)

    # Save as .nii
    save_as_nii(sample_dirs, reoriented_image, output_name, target_resolution)

@unrvl.main_function_decorator(pattern='sample??') # Adjust sample folder pattern as needed (e.g., 'sample??' for sample01, etc.)
def main(sample_dirs):
    args = parse_args() 

    # Check if the output file already exists
    output_file_path = os.path.join(sample_dirs, "niftis", args.output)
    if os.path.exists(output_file_path):
        print(f"Output file {output_file_path} already exists. Skipping.")
        return  # Skip the rest of the main function for this sample_dirs

    load_czi_resample_save_nii(sample_dirs, args.channel, args.xy_res, args.z_res, args.res, args.zoom_order, args.output)

if __name__ == '__main__':
    main()

# To do:
# Create alternate python script for starting from a tif series (e.g., data from UltraII microscope), importing functions from this script