#!/usr/bin/env python3

"""
Use ``img_extend`` from UNRAVEL to load a 3D image, extend one side, and save it as tifs

Usage:
    img_extend -i ochann -o ochann_extended -e 100 -s back -v
"""

import argparse
from pathlib import Path
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', action=SM)
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='path/image or path/image_dir', default=None, action=SM)
    parser.add_argument('-o', '--out_dir_name', help="Output folder name.", required=True, action=SM)
    parser.add_argument('-s', '--side', help="Side to extend. Options: 'front', 'back', 'left', 'right', 'top', 'bottom'. Default: 'front'", default='front', action=SM)
    parser.add_argument('-e', '--extension', help="Number of voxels to extend", type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def extend_one_side_3d_array(ndarray, side, extension):
    """Extend a 3D ndarray on one side ('front', 'back', 'left', 'right', 'top', 'bottom') by X voxels"""
    # TODO: Add option(s) to extend or crop multiple sides

    if side not in ['front', 'back', 'left', 'right', 'top', 'bottom']:
        raise ValueError("Side must be 'front', 'back', 'left', 'right', 'top', or 'bottom'")

    original_shape = ndarray.shape
    extended_shape = list(original_shape)

    if side in ['front', 'back']:
        extended_shape[2] += extension
    elif side in ['left', 'right']:
        extended_shape[0] += extension
    elif side in ['top', 'bottom']:
        extended_shape[1] += extension

    extended_array = np.zeros(extended_shape, dtype=ndarray.dtype)

    if side == 'front':
        extended_array[:, :, extension:] = ndarray
    elif side == 'back':
        extended_array[:, :, :original_shape[2]] = ndarray
    elif side == 'left':
        extended_array[extension:, :, :] = ndarray
    elif side == 'right':
        extended_array[:original_shape[0], :, :] = ndarray
    elif side == 'top':
        extended_array[:, extension:, :] = ndarray
    elif side == 'bottom':
        extended_array[:, :original_shape[1], :] = ndarray

    return extended_array

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    samples = get_samples(args.dirs, args.pattern)

    if samples == ['.']:
        samples[0] = Path.cwd().name

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to tif directory
            cwd = Path(".").resolve()

            sample_path = Path(sample).resolve() if sample != cwd.name else Path().resolve()

            if args.input:
                input_path = Path(args.input).resolve()
            else:
                input_path = Path(sample_path, args.chann_name).resolve()

            # Load image
            img = load_3D_img(input_path, return_res=False)

            # Extend image
            extended_img = extend_one_side_3d_array(img, args.side, args.extension)

            # Define output path
            output_dir = Path(sample_path, args.out_dir_name).resolve()

            # Save extended image
            save_as_tifs(extended_img, output_dir, "xyz")

            progress.update(task_id, advance=1)

    verbose_end_msg()

if __name__ == '__main__':
    main()