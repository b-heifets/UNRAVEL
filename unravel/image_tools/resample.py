#!/usr/bin/env python3

"""
Use ``img_resample`` from UNRAVEL to resample an image.nii.gz and save it.

Usage:
------
    img_resample -i input_image.nii.gz -xy xy_res -z z_res -res target_res [-zo zoom_order] [-o output_image.nii.gz]
"""

import argparse
import nibabel as nib
import numpy as np
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_tools import resample
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(description='Resample a 3D image and save it', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/input_image.nii.gz', required=True, action=SM)
    parser.add_argument('-xy', '--xy_res', help='Original x/y voxel size in microns', required=True, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Original z voxel size in microns', required=True, type=float, action=SM)
    parser.add_argument('-res', '--resolution', help='Target resolution in microns for resampling', required=True, type=float, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order. Default: 0 (nearest-neighbor). Use 1 for linear interpolation.', default=0, type=int, action=SM)
    parser.add_argument('-o', '--output', help='path/output_image.nii.gz. Default: None (saves as path/image_resampled.nii.gz)', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Update the resolution in the header of the resampled image


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii = nib.load(args.input)

    data_type = nii.header.get_data_dtype()
    img = np.asanyarray(nii.dataobj, dtype=data_type).squeeze()

    # Resample the image
    img_resampled = resample(img, args.xy_res, args.z_res, args.resolution, zoom_order=args.zoom_order)

    # Save the resampled image
    resampled_nii = nib.Nifti1Image(img_resampled, nii.affine, nii.header)
    resampled_nii.set_data_dtype(data_type)

    if args.output is None:
        resampled_img_path = args.input.replace('.nii.gz', '_resampled.nii.gz')
    else:
        resampled_img_path = args.output
    nib.save(resampled_nii, resampled_img_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()
