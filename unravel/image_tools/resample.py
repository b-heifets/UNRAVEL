#!/usr/bin/env python3

"""
Use ``img_resample`` from UNRAVEL to resample an image.nii.gz and save it.

Usage:
------
    img_resample -i image.nii.gz -tr 50 [-zo 0] [-o image_resampled.nii.gz] [-v]
"""

import nibabel as nib
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_tools import resample_nii
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/input_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-tr', '--target_res', help='Target resolution in microns for resampling', required=True, type=float, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-zo', '--zoom_order', help='SciPy zoom order. Default: 0 (nearest-neighbor). Use 1 for linear interpolation.', default=0, type=int, action=SM)
    opts.add_argument('-o', '--output', help='path/output_image.nii.gz. Default: None (saves as path/input_image_resampled.nii.gz)', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Add support for anisotropic resampling. Add support for other image formats.


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii = nib.load(args.input)
    resampled_nii = resample_nii(nii, args.target_res, args.zoom_order)

    data_type = nii.header.get_data_dtype()
    resampled_nii.set_data_dtype(data_type)

    if args.output is None:
        resampled_img_path = args.input.replace('.nii.gz', '_resampled.nii.gz')
    else:
        resampled_img_path = args.output
    nib.save(resampled_nii, resampled_img_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()
