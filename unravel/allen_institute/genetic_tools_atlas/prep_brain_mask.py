#!/usr/bin/env python3

"""
Use ``gta_prep_brain_mask`` (``gta_pbm``) from UNRAVEL to downsample an image and save it as tifs. A subset is used to train Ilastik to segment the brain. 

Note:
    - Prepping for and making a brain mask is optional, but can be used to automatically crop images to the brain region.
    - This can save disk space and speed up processing.
    - Resolution levels and x/y pixel spacing (in microns) for the Genetic Tools Atlas (GTA) .zarr files:
    - 0: 0.35, 1: 0.7, 2: 1.4, 3: 2.8, 4: 5.6, 5: 11.2, 6: 22.4, 7: 44.8, 8: 89.6, and 9: 179.2.
    - Z resolution is always 100 µm.
    - We used level 3 (2.8 µm) for the GTA data for Ilastik segmentation
    - If we downsample 40x, the x/y scaling will be 1/40 (0.), so the x/y pixel spacing will be 40 x 2.8 = 112 µm.
    - If -d is not provided, the current directory is used to search for 'ID<asterisk>' dirs to process.
    - If the current dir is a 'ID*' dir, it will be processed.
    - If -d is provided, the specified dirs and/or dirs containing 'ID<asterisk>' dirs will be processed.
    - If -p is not provided, the default pattern for dirs to process is 'ID<asterisk>'.
    - The scale factor can be one int (isotropic) or a list of three ints (anisotropic). Axis order is x, y, z.

Usage:
------
    gta_pbm -i 'tif_dir' [-c 0] [-s 0.025 0.025 1] [-o prep_brain_mask] [-zo 1] [-d list of paths] [-p ID*] [-v]
"""

from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, save_as_tifs
from unravel.core.img_tools import resample
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input image or tif directory.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--channel', help='Channel number for image loading if applicable. Default: 0', default=0, type=int, action=SM)
    opts.add_argument('-s', '--scale', help='Scale factor for downsampling the image. Default: 0.025 0.025 1', default=[0.025, 0.025, 1], nargs='*', type=float, action=SM)
    opts.add_argument('-o', '--output', help='Output directory for the downsampled tif series. Default: prep_brain_mask', default='prep_brain_mask', action=SM)
    opts.add_argument('-zo', '--zoom_order', help='Order for resampling (scipy.ndimage.zoom). Default: 1', default=1, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: ID*', default='ID*', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

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

            # Define output
            output = sample_path / args.output
            if output.exists() and any(output.iterdir()):
                print(f"\n\n    {args.output} already exists. Skipping.\n")
                continue
            output.mkdir(parents=True, exist_ok=True)
            
            # Load the input image
            img_path = sample_path / args.input
            img = load_3D_img(img_path, args.channel, verbose=args.verbose)

            # Downsample the image
            img_resampled = resample(img, scale=args.scale, zoom_order=args.zoom_order)

            # Save the prepped autofluo image as tif series (for ``seg_brain_mask``)
            save_as_tifs(img_resampled, output, "xyz", verbose=args.verbose)

            progress.update(task_id, advance=1)

    verbose_end_msg()
    

if __name__ == "__main__":
    main()
