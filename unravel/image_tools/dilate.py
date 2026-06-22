#!/usr/bin/env python3

"""
Use ``img_dilate`` (``dilate``) from UNRAVEL to dilate a binary mask in a NIfTI image.

Usage: 
------
    img_dilate -i path/image_bin.nii.gz -it 2 [-o path/image_bin_dil{iterations}.nii.gz] [-v]
"""

from rich.traceback import install
from scipy.ndimage import binary_dilation

from unravel.core.img_io import save_as_nii
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.voxel_stats.apply_mask import load_mask


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image.nii.gz', required=True, action=SM)
    reqs.add_argument('-it', '--iterations', help='Number of dilation iterations. Default: 1', type=int, default=1, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='path/image.nii.gz. Default: None (saves as path/image_dilated.nii.gz)', action=SM)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    verbose_start_msg()

    # Load the NIfTI image
    img = load_mask(args.input)

    img[img > 0] = 1

    img_dil = binary_dilation(img, iterations=args.iterations)

    # Save the modified image as a NIfTI file
    output_path = args.output if args.output else str(args.input).replace('.nii.gz', f'_dil{args.iterations}.nii.gz')
    save_as_nii(img_dil, output_path, reference=args.input)

    verbose_end_msg()


if __name__ == '__main__':
    main()
