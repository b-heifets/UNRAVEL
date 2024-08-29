#!/usr/bin/env python3

"""
Use ``img_extend`` from UNRAVEL to load a 3D image, extend one side, and save it as tifs

Usage:
    img_extend -i ochann -o ochann_extended -s front -e 100 [-d <list of paths>] [-p sample??] [-v]
"""

from pathlib import Path
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image or path/image_dir', required=True, action=SM)
    reqs.add_argument('-o', '--out_dir_name', help="Output folder name.", required=True, action=SM)
    reqs.add_argument('-s', '--side', help="Side to extend. Options: 'front', 'back', 'left', 'right', 'top', 'bottom'.", required=True, action=SM)
    reqs.add_argument('-e', '--extension', help="Number of voxels to extend", type=int, required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

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

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            input_path = Path(args.input).resolve()

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