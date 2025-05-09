#!/usr/bin/env python3

"""
Use ``img_pad`` (``pad``) from UNRAVEL to add 15 percent of padding to an image.nii.gz and save it.

Usage:
------
    img_pad -i reg_inputs/autofl_50um.nii.gz [-ort RAS] [-r reg_inputs/autofl_50um.nii.gz] [-o reg_inputs/autofl_50um_pad.nii.gz] [-zero] [-v]
"""

import nibabel as nib
import numpy as np
from rich.traceback import install

from unravel.image_io.nii_info import nii_axis_codes
from unravel.image_io.reorient_nii import reorient_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_tools import pad
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-pad', '--pad_percent', help='Percentage of padding to add to each dimension of the image. Default: 0.15 (15%%).', default=0.15, type=float, action=SM)
    opts.add_argument('-ort', '--ort_code', help='3 letter orientation code of fixed image if not set in fixed_img (e.g., RAS)', action=SM)
    opts.add_argument('-r', '--ref_nii', help='Reference image for setting the orientation code', action=SM)
    opts.add_argument('-o', '--output', help='path/img.nii.gz. Default: None (saves as path/img_pad.nii.gz) ', default=None, action=SM)
    opts.add_argument('-zero', '--zero_origin', help='Set the origin to zero in the affine matrix. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii = nib.load(args.input)

    data_type = nii.header.get_data_dtype()
    img = np.asanyarray(nii.dataobj, dtype=data_type).squeeze()

    # Pad the image
    img = pad(img, pad_percent=args.pad_percent)

    # Save the padded image
    fixed_img_padded_nii = nib.Nifti1Image(img, nii.affine, nii.header)
    fixed_img_padded_nii.set_data_dtype(data_type)

    # Set the orientation of the image (use if not already set correctly in the header; check with ``io_reorient_nii``)
    if args.ort_code: 
        fixed_img_padded_nii = reorient_nii(fixed_img_padded_nii, args.ort_code, zero_origin=args.zero_origin, apply=False, form_code=1)
    elif args.ref_nii:
        ref_nii = nib.load(args.ref_nii)
        ort_code = nii_axis_codes(ref_nii)
        fixed_img_padded_nii = reorient_nii(fixed_img_padded_nii, ort_code, zero_origin=args.zero_origin, apply=False, form_code=1)
    else:
        fixed_img_padded_nii = reorient_nii(fixed_img_padded_nii, nii_axis_codes(nii), zero_origin=args.zero_origin, apply=False, form_code=1)

    if args.output is None:
        padded_img_path = args.input.replace('.nii.gz', '_pad.nii.gz')
    else:
        padded_img_path = args.output
    nib.save(fixed_img_padded_nii, padded_img_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()