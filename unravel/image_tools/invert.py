#!/usr/bin/env python3

"""
Use ``img_invert`` (``invert``) from UNRAVEL to invert a 3D image and save it.

Inputs:
    - path/img<.nii.gz|.tif|.czi|.zarr> or glob pattern(s)
    
Outputs:
    - path/img_inv.<ext>

Note:
    - Inversion is performed as max(image) - x, independent of data type.
    - A warning is issued if the input contains negative values.

Usage:
------
    invert [-i path/img<.nii.gz|.tif|.czi|.zarr> or glob pattern(s)] [-c channel] [-dt dtype] [-v]
"""

from pathlib import Path
import warnings
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, get_extension, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help='path/img.nii.gz or glob pattern(s). Default: *.nii.gz', default='*.nii.gz', action=SM)
    opts.add_argument('-c', '--channel', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    opts.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def invert_img(ndarray, dtype=None):
    """
    Invert an image using data-range inversion.

    Behavior:
        inv = max(image) - x

    Notes:
        - Inversion is based on the image maximum, not the data type range.
        - If the input contains negative values, a warning is issued.
    """
    if not np.issubdtype(ndarray.dtype, np.number):
        raise TypeError(f"invert_img() expects a numeric array. Got {ndarray.dtype}")

    work = ndarray.astype(np.float64, copy=False)

    img_min = float(work.min())
    img_max = float(work.max())

    if img_min < 0:
        warnings.warn(
            f"Input image contains negative values (min={img_min:.3g}); "
            "inversion uses max(image) - x.",
            RuntimeWarning
        )

    inv = img_max - work

    if dtype is not None:
        out_dtype = np.dtype(dtype)
        if np.issubdtype(out_dtype, np.integer):
            info = np.iinfo(out_dtype)
            inv = np.clip(inv, info.min, info.max)
        inv = inv.astype(out_dtype, copy=False)

    return inv

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img_paths = match_files(args.input)

    for img_path in img_paths:
        print(f'\n    Processing image: {img_path}\n')

        img = load_3D_img(img_path, channel=args.channel)

        # Invert the image (max(input_dtype) - x)
        img_inv = invert_img(img, dtype=args.dtype)

        # Save the inverted image
        ext = get_extension(img_path)
        output_path = img_path.parent / str(img_path.name).replace(ext, f'_inv{ext}')
        save_3D_img(img_inv, output_path=output_path, data_type=args.dtype, reference_img=img_path, verbose=args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()