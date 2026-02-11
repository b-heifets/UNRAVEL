#!/usr/bin/env python3

"""
Use ``img_smooth`` (``smooth``) from UNRAVEL to smooth an image.nii.gz and save it.

Note:
    - Sigma is the Gaussian standard deviation.
    - By default, sigma is interpreted in voxels (scipy.ndimage.gaussian_filter).
    - With --mm, sigma is interpreted in millimeters (FSL fslmaths -s).
    - This matches conventions used elsewhere in UNRAVEL (e.g., ``reg``: voxels; ``vstats``: mm).
    - Smoothing is performed in 3D.

Inputs:
    - path/img.nii.gz or glob pattern(s)

Outputs:
    - path/img_s<sigma><.mm|.vx>.nii.gz

Usage:
------
    img_smooth [-i path/img.nii.gz or glob pattern(s)] [-s sigma] [-m] [-v]
"""

from fsl.wrappers import fslmaths
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
    reqs.add_argument('-s', '--sigma', help='Gaussian sigma (standard deviation). Default units: voxels; with --mm: millimeters.', required=True, type=float, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='path/img.nii.gz or glob pattern(s). Default: *.nii.gz', default='*.nii.gz', action=SM)
    opts.add_argument('-m', '--mm', help='Interpret --sigma in millimeters (uses FSL fslmaths -s).', default=False, action='store_true')

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

        units = 'mm' if args.mm else 'vx'
        sigma_str = f"{args.sigma:g}"  # Remove trailing zeros and decimal point if not needed
        output_path = str(Path(img_path).parent / (str(Path(img_path).name).replace('.nii.gz', f'_s{sigma_str}.{units}.nii.gz')))

        print(f'\n    Smoothing the input image\n')
        if args.mm:
            # FSL -s expects sigma in mm and writes the output file itself
            fslmaths(str(img_path)).s(args.sigma).run(output=output_path)
        else:
            img = load_nii(img_path)
            img = gaussian_filter(img, sigma=args.sigma)
            save_3D_img(img, output_path, reference_img=img_path, verbose=args.verbose)
    
    verbose_end_msg()


if __name__ == '__main__':
    main()