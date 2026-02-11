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
    - path/img_s<sigma><mm|vx>.nii.gz

Usage:
------
    img_smooth [-i path/img.nii.gz or glob pattern(s)] [-s sigma] [-m] [-v]
"""

from concurrent.futures import ThreadPoolExecutor
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
    opts.add_argument('-i', '--input', help="path/img.nii.gz or glob pattern(s). Default: '*.nii.gz'", default='*.nii.gz', action=SM)
    opts.add_argument('-m', '--mm', help='Interpret --sigma in millimeters (uses FSL fslmaths -s).', default=False, action='store_true')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def smooth_w_sigma_in_mm(img_path, sigma_mm, output_path):
    """
    Smooth an image with a Gaussian kernel using FSL's fslmaths -s, which expects sigma in millimeters.

    Parameters:
    -----------
    img_path : str or Path
        Path to the input image (e.g., .nii.gz).
    sigma_mm : float
        Standard deviation of the Gaussian kernel in millimeters.
    output_path : str or Path
        Path to save the smoothed image (e.g., .nii.gz).
    """
    fslmaths(str(img_path)).s(sigma_mm).run(output=str(output_path))

def smooth_w_sigma_in_voxels(img_path, sigma_vx, output_path):
    """
    Smooth an image with a Gaussian kernel using scipy.ndimage.gaussian_filter, which expects sigma in voxels.

    Parameters:
    -----------
    img_path : str or Path
        Path to the input image (e.g., .nii.gz).
    sigma_vx : float
        Standard deviation of the Gaussian kernel in voxels.
    output_path : str or Path
        Path to save the smoothed image (e.g., .nii.gz).
    """
    img = load_nii(img_path)
    smoothed_img = gaussian_filter(img, sigma=sigma_vx)
    save_3D_img(smoothed_img, output_path, reference_img=img_path, verbose=Configuration.verbose)

def smooth_image(img_path, sigma, mm=False):
    """
    Smooth an image with a Gaussian kernel, interpreting sigma in either millimeters or voxels.

    Parameters:
    -----------
    img_path : str or Path
        Path to the input image (e.g., .nii.gz).
    sigma : float
        Standard deviation of the Gaussian kernel.
    mm : bool, optional
        If True, interpret sigma in millimeters and use FSL's fslmaths -s. If False, interpret sigma in voxels and use scipy.ndimage.gaussian_filter. Default is False.
    """
    output_path = str(Path(img_path).parent / (str(Path(img_path).name).replace('.nii.gz', f'_s{sigma:g}{"mm" if mm else "vx"}.nii.gz')))

    if mm:
        smooth_w_sigma_in_mm(img_path, sigma, output_path)
    else:
        smooth_w_sigma_in_voxels(img_path, sigma, output_path)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img_paths = match_files(args.input)

    with ThreadPoolExecutor() as executor:
        executor.map(lambda img_path: smooth_image(img_path, args.sigma, mm=args.mm), img_paths)
    
    verbose_end_msg()


if __name__ == '__main__':
    main()