#!/usr/bin/env python3

"""
Use ``io_reorient_nii`` from UNRAVEL to set the orientation of a .nii.gz or its affine matrix.

Usage:
------
    io_reorient_nii -i image.nii.gz -t PIR -a -z

Output:
    - The new .nii.gz file with the new orientation (e.g., image_PIR.nii.gz or image_PIR_applied.nii.gz)

The axis codes are:
    R: Right / L: Left 
    A: Anterior / P: Posterior
    S: Superior / I: Inferior

The orientation code is a 3-letter code that indicates the direction of the axes in the image.

For the RAS+ orientation (default for NIfTI): 
    - The right side is at the positive direction of the x-axis
    - The anterior side is at the positive direction of the y-axis
    - The superior side is at the positive direction of the z-axis

The orientation code also indicates the orientation of the axes in the affine matrix.

Example affine for RAS+ orientation:
    [[1  0  0  0]
    [ 0  1  0  0]
    [ 0  0  1  0]
    [ 0  0  0  1]]

    - The 1st letter is R since the 1st diagonal value is positive (the right side is at the positive direction of the x-axis)
    - The 2nd letter is A since the 2nd diagonal value is positive (the anterior side is at the positive direction of the y-axis)
    - The 3rd letter is S since the 3rd diagonal value is positive (the superior side is at the positive direction of the z-axis)

Example affine for LPS+ orientation:
    [[-1  0  0  0]
    [  0 -1  0  0]
    [  0  0  1  0]
    [  0  0  0  1]]

        -For LPS, the 1st letter is L since the 1st diagonal value is negative.
        -The 2nd letter is P since the 2nd diagonal value is negative.
        -The 3rd letter is S since the 3rd diagonal value is positive.

Example affine for PIR+ orientation (default for CCFv3):
    [[ 0  0  1  0]
    [ -1  0  0  0]
    [  0 -1  0  0]
    [  0  0  0  1]]

For PIR:
    First letter determination: 
        -The 1st column has a non-zero value at the 2nd row, so the 1st letter is either A or P (2nd letter of the default 'RAS' orientation code).
        -Since the valud is negative, the 1st letter is P
    Second letter determination:
        -The 2nd column has a non-zero value at the 3rd row, so the 2nd letter is either S or I (3rd letter of the default 'RAS' orientation code).
        -Since the value is negative, the 2nd letter is I
    Third letter determination:
        -The 3rd column has a non-zero value at the 1st row, so the 3rd letter is either R or L (1st letter of the default 'RAS' orientation code).
        -Since the value is positive, the 3rd letter is R
"""

import argparse
import nibabel as nib
import numpy as np
from nibabel.orientations import axcodes2ornt, ornt_transform, io_orientation, aff2axcodes, apply_orientation
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-t', '--target_ort', help='Target orientation axis codes (e.g., RAS)', required=True, action=SM)
    parser.add_argument('-z', '--zero_origin', help='Provide flag to zero the origin of the affine matrix.', action='store_true', default=False)
    parser.add_argument('-a', '--apply', help='Provide flag to apply the new orientation to the ndarray data.', action='store_true', default=False)
    parser.add_argument('-fc', '--form_code', help='Set the sform and qform codes for spatial coordinate type (1 = scanner; 2 = aligned)', type=int, default=None)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def transform_nii_affine(nii, target_ort, zero_origin=False):
    """Transform the affine matrix of a NIfTI image to a target orientation and return the new affine matrix
    
    Args:
        nii (nibabel.nifti1.Nifti1Image): NIfTI image
        target_ort (str): Target orientation axis codes (e.g., RAS)
        zero_origin (bool): Zero the origin of the affine matrix. Default: False
    """

    # Get the current axis codes
    current_axcodes_tuple = aff2axcodes(nii.affine) 
    current_axcodes = ''.join(current_axcodes_tuple) 
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nCurrent affine matrix ({current_axcodes}): \n{nii.affine}')

    # Get the current orientation
    current_orientation = axcodes2ornt(current_axcodes_tuple)

    # Get the index of the target orientation
    current_ort_first_col_index = int(current_orientation[0][0])
    current_ort_second_col_index = int(current_orientation[1][0])
    current_ort_third_col_index = int(current_orientation[2][0])

    # Convert the current affine to the target orientation
    target_orientation = axcodes2ornt(target_ort)

    # Get the sign of the target orientation
    sign_of_first_target_direction = target_orientation[0][1]
    sign_of_second_target_direction = target_orientation[1][1]
    sign_of_third_target_direction = target_orientation[2][1]

    # Get the index of the target orientation
    new_ort_first_col_index = int(target_orientation[0][0])
    new_ort_second_col_index = int(target_orientation[1][0])
    new_ort_third_col_index = int(target_orientation[2][0])

    # Make an affine matrix for the target orientation
    new_affine = np.zeros((4,4))
    new_affine[:,3] = 1

    # Set the columns of the new affine matrix to the target orientation
    new_affine[new_ort_first_col_index, 0] = sign_of_first_target_direction * np.abs(nii.affine[current_ort_first_col_index, 0]) 
    new_affine[new_ort_second_col_index, 1] = sign_of_second_target_direction * np.abs(nii.affine[current_ort_second_col_index, 1]) 
    new_affine[new_ort_third_col_index, 2] = sign_of_third_target_direction * np.abs(nii.affine[current_ort_third_col_index, 2])

    # Set the origin of the new affine matrix to the origin of the current affine matrix
    new_affine[0:3,3] = nii.affine[0:3,3]

    # Zero the origin of the affine matrix
    if zero_origin:
        for i in range(3):
            new_affine[i,3] = 0

    # Get the axis codes of the new affine
    new_axcodes_tuple = nib.orientations.aff2axcodes(new_affine) 
    new_axcodes = ''.join(new_axcodes_tuple) 
    print(f'\nNew affine matrix ({new_axcodes}): \n{new_affine}')

    return new_affine

def reorient_nii(nii, target_ort, zero_origin=False, apply=False, form_code=None):
    """Reorient a NIfTI image or its affine matrix to a target orientation.

    Args:
        nii_path (str): Path to the NIfTI image
        target_ort (str): Target orientation axis codes (e.g., RAS)
        zero_origin (bool): Zero the origin of the affine matrix. Default: False
        apply (bool): Apply the new orientation to the ndarray data. Default: False
        form_code (int): Set the sform and qform codes for spatial coordinate type (1 = scanner; 2 = aligned). Default: None (get from the input NIfTI image)

    Returns:
        If apply True: new_nii (nibabel.nifti1.Nifti1Image): NIfTI image with the new orientation
        If apply False: new_affine (np.ndarray): New affine matrix
        
    """

    # Optionally apply the orientation change to the image data
    if apply:
        print('Applying orientation change to the image data...')
        img = nii.get_fdata(dtype=np.float32)
        current_orientation = io_orientation(nii.affine)
        target_orientation = axcodes2ornt(target_ort)
        orientation_change = ornt_transform(current_orientation, target_orientation)
        img = apply_orientation(img, orientation_change)
    else:
        img = nii.get_fdata(dtype=np.float32)


    # Check data type
    data_type = nii.header.get_data_dtype()

    # For integer data types, round the values to the nearest integer
    if np.issubdtype(data_type, np.integer):
        img = np.round(img).astype(data_type)

    # Get the new affine matrix
    new_affine = transform_nii_affine(nii, target_ort, zero_origin=zero_origin)

    # Make the new NIfTI image
    new_nii = nib.Nifti1Image(img, new_affine)
    new_nii.header.set_data_dtype(data_type)

    # Set the header information
    new_nii.header['xyzt_units'] = 10 # mm, s
    new_nii.header['regular'] = b'r'

    if form_code:
        new_nii.header.set_qform(new_affine, code=form_code)
        new_nii.header.set_sform(new_affine, code=form_code)
    else: 
        new_nii.header.set_qform(new_affine, code=int(nii.header['qform_code']))
        new_nii.header.set_sform(new_affine, code=int(nii.header['sform_code']))

    return new_nii


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii = nib.load(args.input)
    new_nii = reorient_nii(nii, args.target_ort, zero_origin=args.zero_origin, apply=args.apply, form_code=args.form_code)

    # Save the new .nii.gz file
    if args.output: 
        nib.save(new_nii, args.output)
    else:
        if args.apply:
            nib.save(new_nii, args.input.replace('.nii.gz', f'_{args.target_ort}_applied.nii.gz'))
        else:
            nib.save(new_nii, args.input.replace('.nii.gz', f'_{args.target_ort}.nii.gz'))

    verbose_end_msg()


if __name__ == '__main__':
    main()