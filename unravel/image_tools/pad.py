#!/usr/bin/env python3

"""
Use ``img_pad`` from UNRAVEL to add 15 percent of padding to an image.nii.gz and save it.

Usage:
------
    img_pad -i reg_inputs/autofl_50um.nii.gz
"""

import argparse
import nibabel as nib
import numpy as np
from rich.traceback import install

from unravel.image_io.nii_info import nii_axis_codes
from unravel.image_io.reorient_nii import reorient_nii
from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_tools import pad
from unravel.core.utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Adds 15 percent of padding to an image and saves it', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code of fixed image if not set in fixed_img (e.g., RAS)', action=SM)
    parser.add_argument('-r', '--ref_nii', help='Reference image for setting the orientation code', action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz. Default: None (saves as path/img_pad.nii.gz) ', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_cmd_and_times
def main(): 
    args = parse_args()

    nii = nib.load(args.input)

    data_type = nii.header.get_data_dtype()
    img = np.asanyarray(nii.dataobj, dtype=data_type).squeeze()

    # Pad the image
    img = pad(img, pad_width=0.15)

    # Save the padded image
    fixed_img_padded_nii = nib.Nifti1Image(img, nii.affine, nii.header)
    fixed_img_padded_nii.set_data_dtype(data_type)

    # Set the orientation of the image (use if not already set correctly in the header; check with ``io_reorient_nii``)
    if args.ort_code: 
        fixed_img_padded_nii = reorient_nii(fixed_img_padded_nii, args.ort_code, zero_origin=True, apply=False, form_code=1)
    else:
        ref_nii = nib.load(args.ref_nii)
        ort_code = nii_axis_codes(ref_nii)
        fixed_img_padded_nii = reorient_nii(fixed_img_padded_nii, ort_code, zero_origin=True, apply=False, form_code=1)

    if args.output is None:
        padded_img_path = args.input.replace('.nii.gz', '_pad.nii.gz')
    else:
        padded_img_path = args.output
    nib.save(fixed_img_padded_nii, padded_img_path)


if __name__ == '__main__' or __name__ == 'unravel.image_tools.pad':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose

if __name__ == '__main__':
    main()