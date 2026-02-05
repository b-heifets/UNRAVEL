#!/usr/bin/env python3

"""
Use ``reg_background`` (``rbg``) from UNRAVEL to estimate and save the background of a 3D image using a rolling-ball-like method.

Notes:
    - Provides a background image for registration when no autofluorescence channel is available (e.g., c-Fos IF).
    - Supports uint8 and uint16 images only.

Inputs:
    - path/img<.nii.gz|.tif|.czi|.zarr> or glob pattern(s)

Outputs:
    - path/img_rb<radius>_bg.<ext>


Usage:
------
    reg_background [-i input] [-o output] [-rb radius] [-c channel] [-dt dtype] [-v]
"""


from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img, resolve_path
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Path to full res image (relative to ./sample??/) or glob pattern (e.g., '*.czi'). First match used.", required=True, action=SM)
    reqs.add_argument('-o', '--output', help='Output filename (relative to ./sample??/)', required=True, action=SM)
    reqs.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels', required=True, type=int, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--channel', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    opts.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)
    opts.add_argument('-th', '--threads', help='Number of threads for rolling ball background estimation. Default: 8', default=8, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def process_slice(slice2d, struct_element):
    """Return background estimate via morphological opening."""
    slice2d = np.ascontiguousarray(slice2d)
    bg = cv2.morphologyEx(slice2d, cv2.MORPH_OPEN, struct_element)
    return bg

@print_func_name_args_times()
def rolling_ball_background_opencv_parallel(ndarray, radius, threads=8):
    """Return background estimate per-slice using morphological opening (rolling ball approximation)."""
    if radius is None or radius < 1:
        raise ValueError("rb_radius must be an integer >= 1")

    if ndarray.dtype not in (np.uint8, np.uint16):
        raise TypeError(f"Only uint8/uint16 supported. Got {ndarray.dtype}")

    struct_element = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (2 * radius + 1, 2 * radius + 1) # 2D disk
    )

    bg_img = np.empty_like(ndarray)
    num_workers = min(len(ndarray), int(threads))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        for i, bg_slice in enumerate(executor.map(process_slice, ndarray, [struct_element] * len(ndarray))):
            bg_img[i] = bg_slice

    return bg_img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    out_dtype = np.dtype(args.dtype)
    if out_dtype not in (np.uint8, np.uint16):
        raise TypeError(f"--dtype must be uint8 or uint16. Got {out_dtype}")

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(len(sample_paths), "[red]Processing samples...")
    with Live(progress):
        for sample_path in sample_paths:

            # Define output
            output = sample_path / args.output
            if output.exists():
                print(f"\n\n    {args.output} already exists. Skipping.\n")
                continue
            
            # Define input image path
            img_path = resolve_path(sample_path, args.input)

            # Load the image
            img = load_3D_img(img_path, channel=args.channel)

            # Create background estimate using rolling ball method
            img_bg = rolling_ball_background_opencv_parallel(img, radius=args.rb_radius, threads=args.threads)

            # Save the background image
            output.parent.mkdir(parents=True, exist_ok=True)
            save_3D_img(img_bg, output_path=output, data_type=args.dtype, verbose=args.verbose)

            progress.update(task_id, advance=1)
    
    verbose_end_msg()


if __name__ == '__main__':
    main()