#!/usr/bin/env python3

"""
Use ``img_resample`` from UNRAVEL to resample an image.nii.gz and save it.

Usage:
------
    img_resample -i input_image.nii.gz -res target_res [-zo zoom_order] [-o output_image.nii.gz] [-v]
"""

import argparse
import nibabel as nib
import numpy as np
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_io import nii_to_ndarray
from unravel.core.img_tools import resample
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/input_image.nii.gz', required=True, action=SM)
    parser.add_argument('-tr', '--target_res', help='Target resolution in microns for resampling', required=True, type=float, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order. Default: 0 (nearest-neighbor). Use 1 for linear interpolation.', default=0, type=int, action=SM)
    parser.add_argument('-o', '--output', help='path/output_image.nii.gz. Default: None (saves as path/input_image_resampled.nii.gz)', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Add support for anisotropic resampling. Add support for other image formats.

def create_resampled_nii(img, nii, original_res_in_um, target_res, zoom_order):
    """Resample the image and create a new NIfTI image with updated affine and header.
    
    Parameters:
    -----------
    img : numpy.ndarray
        Image data as a numpy array.
        
    nii : nibabel.nifti1.Nifti1Image
        NIfTI image object.
        
    original_res_in_um : float
        Original resolution of the image in micrometers.
        
    target_res : float
        Target resolution in micrometers for resampling.
        
    zoom_order : int
        SciPy zoom order. Default: 0 (nearest-neighbor). Use 1 for linear interpolation.
        
    Returns:
    --------
    resampled_nii : nibabel.nifti1.Nifti1Image
        Resampled NIfTI image object.
        """
    img_resampled = resample(img, original_res_in_um, original_res_in_um, target_res, zoom_order=zoom_order)

    # Update the affine and header
    affine_ndarray = np.array(nii.affine)
    new_affine = affine_ndarray * (target_res / original_res_in_um)
    new_header = nii.header.copy()
    new_header.set_zooms((target_res, target_res, target_res))

    # Create the resampled NIfTI image
    resampled_nii = nib.Nifti1Image(img_resampled, new_affine, new_header)
    return resampled_nii


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii = nib.load(args.input)
    img = nii_to_ndarray(nii)
    data_type = nii.header.get_data_dtype()
    zooms = nii.header.get_zooms()
    original_res_in_mm = zooms[0]
    original_res_in_um = original_res_in_mm * 1000

    resampled_nii = create_resampled_nii(img, nii, original_res_in_um, args.target_res, args.zoom_order)
    resampled_nii.set_data_dtype(data_type)

    if args.output is None:
        resampled_img_path = args.input.replace('.nii.gz', '_resampled.nii.gz')
    else:
        resampled_img_path = args.output
    nib.save(resampled_nii, resampled_img_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()
