#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img, save_as_tifs
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Load 3D image, extend one side, and save as tifs', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='path/image or path/image_dir', default=None, metavar='')
    parser.add_argument('-o', '--out_dir_name', help="Output folder name.", metavar='')
    parser.add_argument('-s', '--side', help="Side to extend. Options: 'front', 'back', 'left', 'right', 'top', 'bottom'. Default: 'front'", default='front', metavar='')
    parser.add_argument('-e', '--extension', help="Number of voxels to extend", type=int, metavar='')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """
Run script from the experiment directory containing sample?? folders or a sample?? folder.
Example usage: extend_image.py -i ochann -o ochann_extended -v
"""
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


def main():
    args = parse_args()

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
            dtype = img.dtype
            save_as_tifs(extended_img, output_dir, "xyz", data_type=dtype)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()