#!/usr/bin/env python3

import ants
import argparse
import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from unravel_config import Configuration
from unravel_utils import print_func_name_args_times, print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Warp to/from atlas space and registration input space', formatter_class=SuppressMetavar)
    parser.add_argument('-ro', '--reg_outputs', help='path/reg_outputs', required=True, action=SM)
    parser.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz', required=True, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/moving_image.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/output.nii.gz', required=True, action=SM)
    parser.add_argument('-inv', '--inverse', help='Perform inverse warping (use flag if -f & -m are opposite from reg.py)', default=False, action='store_true')
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (linear [default], nearestNeighbor, multiLabel).', default='linear', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity if flag provided', default=False, action='store_true')
    parser.epilog = """
# Example of forward warping atlas to tissue space:
warp.py -m atlas_img.nii.gz -f reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -ro reg_outputs -o warp/atlas_in_tissue_space.nii.gz -inp multiLabel -v

# Example of inverse warping tissue to atlas space:
warp.py -m reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -f atlas_img.nii.gz -ro reg_outputs -o warp/tissue_in_atlas_space.nii.gz -inv -v

Prereq: reg.py
"""
    return parser.parse_args()


@print_func_name_args_times()
def warp(reg_outputs_path, moving_img_path, fixed_img_path, output_path, inverse, interpol):
    """
    Applies the transformations to an image using ANTsPy.

    Parameters:
    moving_img_name (str): Path to the image to be transformed.
    reg_outputs_path (str): Path to the reg_outputs folder (contains tranformation files)
    direction: direction of warping (forward or reverse)
    fixed_img_name (str): Path to the reference image for applying the transform.
    output_path (str): Path where the transformed image will be saved.
    inverse (bool): If True, apply the inverse transformation. Defaults to False.
    interpol (str): Type of interpolation (e.g., 'Linear', 'NearestNeighbor', etc.)
    """

    # Get the transforms prefix
    transforms_prefix_file = next(reg_outputs_path.glob(f"*1Warp.nii.gz"), None)
    if transforms_prefix_file is None:
        raise FileNotFoundError(f"No '1Warp.nii.gz' file found in {reg_outputs_path}")
    transforms_prefix = str(transforms_prefix_file.name).replace("1Warp.nii.gz", "")

    # Load images (With forward warping, fixed/moving match reg.py. They are reversed for inverse warping.)
    fixed_img_ants = ants.image_read(fixed_img_path)
    moving_img_ants = ants.image_read(moving_img_path) 

    # Apply the transformations
    if inverse:
        # Create a dummy moving image filled with zeros
        dummy_moving = ants.make_image(moving_img_ants.shape, voxval=0, spacing=moving_img_ants.spacing, origin=moving_img_ants.origin, direction=moving_img_ants.direction)

        # Specify the transformations
        transforms = [
            str(reg_outputs_path / f'{transforms_prefix}1InverseWarp.nii.gz'), 
            str(reg_outputs_path / f'{transforms_prefix}0GenericAffine.mat') 
        ]

        # Apply the transformations to generate a composite deformation field
        deformation_field = ants.apply_transforms(
            fixed=moving_img_ants, 
            moving=dummy_moving, 
            transformlist=transforms, 
            whichtoinvert=[False, True], 
            compose=f'{reg_outputs_path}/' # dir to output comptx.nii.gz
        )

        # Applying transformations from registration and initial alignment
        transforms = [
            str(reg_outputs_path / f'{transforms_prefix}init_tform.mat'), # Initial transformation matrix 
            str(reg_outputs_path / 'comptx.nii.gz') # Composite transformation field
        ]
        warped_img_ants = ants.apply_transforms(fixed=fixed_img_ants, moving=moving_img_ants, transformlist=transforms, interpolator=interpol)

    else: 
        deformation_field = str(reg_outputs_path / f'{transforms_prefix}1Warp.nii.gz')
        generic_affine_matrix = str(reg_outputs_path / f'{transforms_prefix}0GenericAffine.mat')
        initial_transform_matrix = str(reg_outputs_path / f'{transforms_prefix}init_tform.mat')
        warped_img_ants = ants.apply_transforms(
            fixed=fixed_img_ants,
            moving=moving_img_ants,
            transformlist=[deformation_field, generic_affine_matrix, initial_transform_matrix],
            interpolator=interpol
        )
    
    # Convert the ANTsImage to a numpy array 
    warped_img = warped_img_ants.numpy()

    # Round the floating-point label values to the nearest integer
    warped_img = np.round(warped_img)

    # Convert dtype of warped image to match the moving image
    moving_img_nii = nib.load(moving_img_path) 
    data_type = moving_img_nii.header.get_data_dtype()
    if np.issubdtype(data_type, np.unsignedinteger):
        warped_img[warped_img < 0] = 0 # If output_dtype is unsigned, set negative values to zero
    warped_img = warped_img.astype(data_type)

    # Convert the warped image to NIfTI, copy relevant header information, and save it
    fixed_img_nii = nib.load(fixed_img_path) 
    warped_img_nii = nib.Nifti1Image(warped_img, fixed_img_nii.affine.copy(), fixed_img_nii.header.copy())
    warped_img_nii.set_data_dtype(data_type)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    nib.save(warped_img_nii, output_path)


def main(): 

    reg_outputs_path = Path(args.reg_outputs).resolve()
    moving_img_path = str(Path(args.moving_img).resolve())
    fixed_img_path = str(Path(args.fixed_img).resolve())

    warp(reg_outputs_path, moving_img_path, fixed_img_path, args.output, args.inverse, args.interpol)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()