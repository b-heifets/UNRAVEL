#!/usr/bin/env python3

"""
Use ``pngs_to_mip_tif.py`` from UNRAVEL to convert a set of PNGs to a single TIF file containing the maximum intensity projections (MIPs) of the PNGs.

Usage:
------
    pngs_to_mip_tif.py -i path/to/pngs -o path/to/output.tif
"""

import imageio
import numpy as np
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to folder with png files', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='Output path for the saved .tif file.', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def max_intensity_projection(input_folder, output_tif):
    # Find all PNG images
    png_files = match_files('*.png', input_folder)
    if not png_files:
        raise ValueError(f"No PNG files found in {input_folder}")

    # Load all images into a stack
    stack = [imageio.imread(f) for f in png_files]
    stack = np.stack(stack, axis=0)

    # Compute max intensity projection
    mip = stack.max(axis=0)

    # Save as tif
    imageio.imwrite(output_tif, mip.astype(stack[0].dtype))
    print(f"Saved max projection as {output_tif}")

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the PNGs
    max_intensity_projection(args.input, args.output)

    verbose_end_msg()


if __name__ == '__main__':
    main()