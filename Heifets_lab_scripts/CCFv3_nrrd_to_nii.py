#!/usr/bin/env python3

import argparse
import nrrd
import nibabel as nib
import numpy as np
from rich.traceback import install
from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Convert CCFv3 images from .nrrd (PIR) to .nii.gz (PIR).', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-r', '--resolution', help='Resolution (xyz voxel size in microns)', required=True, type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


@print_func_name_args_times()
def CCFv3_nrrd_to_nii(input_image, output_image, resolution):

    # Load the NRRD file
    nrrd_data, header = nrrd.read(input_image)

    # Convert the NRRD data to a Numpy array
    img = np.array(nrrd_data)

    # Convert microns to millimeters by dividing by 1000 (Neuroimaging conventions usually use mm)
    voxel_size_mm = resolution / 1000

    # Create an affine matrix for the PIR orientation and the CCFv3-2020 origin
    affine = np.array([
        [0, 0, voxel_size_mm, -5.695000],  
        [-voxel_size_mm, 0, 0, 5.350000],  
        [0, -voxel_size_mm, 0, 5.220000],  
        [0, 0, 0, 1]
    ])

    # Create the NIfTI image with the corrected PIL-oriented affine matrix
    nifti_img = nib.Nifti1Image(img, affine)

    # Set the header information
    nifti_img.header['xyzt_units'] = 10
    nifti_img.header['qform_code'] = 1 # Scanner aligned
    nifti_img.header['sform_code'] = 1 # Scanner aligned

    # Get the data type of the template image
    input_dtype = nifti_img.header.get_data_dtype()

    # Set the data type of the NIfTI image to match the template image
    nifti_img.set_data_dtype(input_dtype)

    # Set the last four elements of pixdim to 0
    nifti_img.header['pixdim'][4:] = [0, 0, 0, 0]

    # Set the regular flag to 'r'
    nifti_img.header['regular'] = b'r'

    # Save the NIfTI file with the corrected header
    nib.save(nifti_img, output_image)

def main():

    CCFv3_nrrd_to_nii(args.input, args.output, args.resolution)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
