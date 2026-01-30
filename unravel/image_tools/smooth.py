#!/usr/bin/env python3

"""
Use ``img_smooth`` (``smooth``) from UNRAVEL to smooth an image.nii.gz and save it.

Usage:
------
    img_smooth -sm <sigma_value> [-i path/img.nii.gz or glob pattern(s)] [-r path/ref_img.nii.gz] [-o path/img_smoothed.nii.gz] [-v]
"""

from pathlib import Path
from rich import print
from rich.traceback import install
from scipy.ndimage import gaussian_filter

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_nii, save_3D_img
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-sm', '--smooth', help='Sigma value for smoothing the image (e.g., 1.0)', required=True, type=float, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='path/img.nii.gz or glob pattern(s). Default: *.nii.gz', default='*.nii.gz', action=SM)
    opts.add_argument('-r', '--ref_nii', help='Path to reference image for .nii.gz metadata', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img_paths = match_files(args.input)

    for img_path in img_paths:
        print(f'\n    Processing image: {img_path}\n')
        img = load_nii(img_path)

        print(f'\n    Smoothing the input image\n')
        img = gaussian_filter(img, sigma=args.smooth)

        output_path = str(Path(img_path).parent / (str(Path(img_path).name).replace('.nii.gz', '_smoothed.nii.gz')))
        save_3D_img(img, output_path, reference_img=args.ref_nii, verbose=args.verbose)
    
    verbose_end_msg()


if __name__ == '__main__':
    main()