#!/usr/bin/env python3

"""
Use ``img_invert`` (``invert``) from UNRAVEL to invert a 3D image and save it.

Inputs:
    - path/img<.nii.gz|.tif|.czi|.zarr> or glob pattern(s)
    
Outputs:
    - path/img_inv.<ext>

Note:
    - Only uint8 and uint16 images are supported.

Usage:
------
    img_invert [-i path/img<.nii.gz|.tif|.czi|.zarr> or glob pattern(s)] [-c channel] [-dt dtype] [-v]
"""

from pathlib import Path
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


def _promote_dtype_for_invert_img(ndarray_dtype: np.dtype) -> np.dtype:
    """
    Promote uint8 to int16 and uint16 to int32 for intermediate calculations in invert_img() to prevent overflow/underflow.
    """
    if ndarray_dtype == np.uint8:
        return np.int16
    if ndarray_dtype == np.uint16:
        return np.int32
    raise TypeError(f"Expected uint8 or uint16, got {ndarray_dtype}.")


@print_func_name_args_times()
def invert_img(ndarray, dtype=None):
    """
    Invert a uint8/uint16 image using the full input dtype range.

    Behavior:
        inv = max(input_dtype) - x

    Notes:
        - Supports only uint8 and uint16 (deterministic, unambiguous).
        - Float images are intentionally disallowed.
    """
    if ndarray.dtype not in (np.uint8, np.uint16):
        raise TypeError(f"invert_img() expects uint8 or uint16. Got {ndarray.dtype}.")

    out_dtype = np.dtype(dtype) if dtype is not None else ndarray.dtype
    if out_dtype not in (np.uint8, np.uint16):
        raise TypeError(f"Output dtype must be uint8 or uint16. Got {out_dtype}.")

    in_max = np.iinfo(ndarray.dtype).max

    img_dtype = _promote_dtype_for_invert_img(ndarray.dtype)
    img = ndarray.astype(img_dtype, copy=False)

    img_inv = in_max - img

    # Clip only matters when converting uint16 -> uint8
    out_info = np.iinfo(out_dtype)
    img_inv = np.clip(img_inv, out_info.min, out_info.max)

    return img_inv.astype(out_dtype, copy=False)


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