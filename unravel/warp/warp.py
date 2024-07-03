#!/usr/bin/env python3

"""
Use ``warp`` from UNRAVEL to warp to/from atlas space and registration input space

Usage for forward warping atlas to tissue space:
------------------------------------------------
    warp -m atlas_img.nii.gz -f reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -ro reg_outputs -o warp/atlas_in_tissue_space.nii.gz -inp multiLabel -v

Usage for inverse warping tissue to atlas space:
------------------------------------------------
    warp -m reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -f atlas_img.nii.gz -ro reg_outputs -o warp/tissue_in_atlas_space.nii.gz -inv -v

Prereq: 
    ``reg``

Note: 
    This warps padded images in ./reg_outputs (i.e., images that match the padded fixed reg input). For unpadded final images, use ``warp_to_fixed`` and ``warp_to_atlas``.
"""

import ants
import argparse
import numpy as np
import nibabel as nib
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-ro', '--reg_outputs', help='path/reg_outputs', required=True, action=SM)
    parser.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz', required=True, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/moving_image.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/output.nii.gz', required=True, action=SM)
    parser.add_argument('-inv', '--inverse', help='Perform inverse warping (use flag if -f & -m are opposite from ``reg``)', default=False, action='store_true')
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default], nearestNeighbor, multiLabel).', default='bSpline', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def warp(reg_outputs_path, moving_img_path, fixed_img_path, output_path, inverse, interpol):
    """
    Applies the transformations to an image using ANTsPy.

    Parameters:
    reg_outputs_path (Path): Path to the reg_outputs folder (contains transformation files)
    moving_img_path (str): Path to the image to be transformed.
    fixed_img_path (str): Path to the reference image for applying the transform.
    output_path (str): Path where the transformed image will be saved.
    inverse (bool): If True, apply the inverse transformation. Defaults to False.
    interpol (str): Type of interpolation (e.g., 'Linear', 'NearestNeighbor', etc.)
    """

    # Get the transforms prefix
    transforms_prefix_file = next(reg_outputs_path.glob(f"*1Warp.nii.gz"), None)
    if transforms_prefix_file is None:
        raise FileNotFoundError(f"No '1Warp.nii.gz' file found in {reg_outputs_path}")
    transforms_prefix = str(transforms_prefix_file.name).replace("1Warp.nii.gz", "")

    # Load images
    fixed_img_ants = ants.image_read(fixed_img_path)
    moving_img_ants = ants.image_read(moving_img_path) 

    # Paths to the transformation files
    generic_affine_matrix = str(reg_outputs_path / f'{transforms_prefix}0GenericAffine.mat')
    initial_transform_matrix = str(reg_outputs_path / f'{transforms_prefix}init_tform.mat')
    if not Path(reg_outputs_path / f'{transforms_prefix}init_tform.mat').exists():
        initial_transform_matrix = str(reg_outputs_path / 'init_tform.mat') # For backward compatibility


    # Apply the transformations
    if inverse:
        deformation_field_inverse = str(reg_outputs_path / f'{transforms_prefix}1InverseWarp.nii.gz')
        transformlist = [initial_transform_matrix, generic_affine_matrix, deformation_field_inverse]
        whichtoinvert = [True, True, False]
    else:
        deformation_field = str(reg_outputs_path / f'{transforms_prefix}1Warp.nii.gz')
        transformlist = [deformation_field, generic_affine_matrix, initial_transform_matrix]
        whichtoinvert = [False, False, False]

    warped_img_ants = ants.apply_transforms(
        fixed=fixed_img_ants,
        moving=moving_img_ants,
        transformlist=transformlist,
        whichtoinvert=whichtoinvert,
        interpolator=interpol
    )

    # Convert the ANTsImage to a numpy array 
    warped_img = warped_img_ants.numpy()

    # Round the floating-point label values to the nearest integer
    warped_img = np.round(warped_img)

    # Convert dtype of warped image to match the moving image
    moving_img_nii = nib.load(moving_img_path) 
    data_type = moving_img_nii.header.get_data_dtype()
    warped_img[warped_img < 0] = 0 # Removes negative values from bSpline interpolation
    warped_img = warped_img.astype(data_type)

    # Save the transformed image with appropriate header and affine information
    fixed_img_nii = nib.load(fixed_img_path) 
    warped_img_nii = nib.Nifti1Image(warped_img, fixed_img_nii.affine.copy(), fixed_img_nii.header.copy())
    warped_img_nii.set_data_dtype(data_type)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    nib.save(warped_img_nii, output_path)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    reg_outputs_path = Path(args.reg_outputs).resolve()
    moving_img_path = str(Path(args.moving_img).resolve())
    fixed_img_path = str(Path(args.fixed_img).resolve())

    warp(reg_outputs_path, moving_img_path, fixed_img_path, args.output, args.inverse, args.interpol)

    verbose_end_msg()


if __name__ == '__main__':
    main()