#!/usr/bin/env python3

"""
Use ``img_rb`` (``rb``) from UNRAVEL to perform rolling ball background subtraction on a 3D image or a test 2D TIFF image.

Note:
    - Radius for rolling ball subtraction should be ~ 1.0 to 2.0 times the size of the features of interest
    - Larger radii will remove more background, but may also remove some of the features of interest
    - Smaller radii will remove less background, but may leave some background noise

Usage:
------
    img_rb -i path/img.tif -o path/img_rb.tif -rb 4 [-c 1] [-dt uint16] [-th 8] [-t] [-v]
"""

from pathlib import Path
import cv2
import numpy as np
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples
from unravel.core.img_io import load_3D_img, save_3D_img, resolve_path
from unravel.core.img_tools import rolling_ball_subtraction_opencv_parallel


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Path to full res image (relative to ./sample??/ [or cwd w/ -t]) or glob pattern (e.g., '*.czi'). First match used.", required=True, action=SM)
    reqs.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels.', required=True, type=int, action=SM)
    reqs.add_argument('-o', '--output', help='Output filename (relative to ./sample??/) or, if -t, path to save the output TIFF file.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-t', '--test', help='Run a test with a 2D TIFF image. Default: False', action='store_true', default=False)
    opts.add_argument('-c', '--channel', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    opts.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: uint16', default="uint16", action=SM)
    opts.add_argument('-th', '--threads', help='Number of threads for rolling ball background estimation. Default: 8', default=8, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def load_tif(tif_path):
    '''Load a single tif file using OpenCV and return ndarray.'''
    img = cv2.imread(tif_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f'Could not load the TIFF file from {tif_path}')
    return img

def rolling_ball_subtraction(img, radius):
    '''Subtract background from image using a rolling ball algorithm.'''
    kernel_size = 2 * radius + 1
    struct_element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)) # 2D disk
    background = cv2.morphologyEx(img, cv2.MORPH_OPEN, struct_element)
    subtracted_img = cv2.subtract(img, background)
    return subtracted_img

def save_tif(img, output_path):
    '''Save an image as a tif file.'''
    cv2.imwrite(output_path, img)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.test:

        # Load the image
        img = load_tif(args.input)

        # Apply rolling ball subtraction
        img = rolling_ball_subtraction(img, args.rb_radius)
        print(f'Applied rolling ball subtraction with radius {args.rb_radius}.')

        # Save the processed image
        output_path = args.output if args.output is not None else args.input.replace('.tif', f'_rb{args.rb_radius}.tif')
        save_tif(img, output_path)

    else:

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

                # Create background estimate using rolling ball method and subtract it from the original image
                img_bg = rolling_ball_subtraction_opencv_parallel(img, radius=args.rb_radius, threads=args.threads)

                # Save the background-subtracted image
                output.parent.mkdir(parents=True, exist_ok=True)
                save_3D_img(img_bg, output_path=output, data_type=args.dtype, verbose=args.verbose)

                progress.update(task_id, advance=1)


    verbose_end_msg()


if __name__ == '__main__':
    main()
