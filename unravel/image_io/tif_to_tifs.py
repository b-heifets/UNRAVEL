#!/usr/bin/env python3

"""
Use ``io_tif_to_tifs`` (``t2t``) from UNRAVEL to load a 3D .tif  or .ome.tif image and save it as tifs.

Input: 
    - path/image.tif (can use glob patterns)

Outputs:
    - <tif_dir>/slice_0000.tif, <tif_dir>/slice_0001.tif, ...
    - tif_dir may be specified with -t flag or it will default to <image_name>_tifs
    - parameters/metadata.txt (if -m flag is used)

Next command: 
    ``io_metadata`` to specify voxel sizes and image dimensions to parameters/metadata.txt (if metadata is not extractable)
    ``reg_prep`` to prep autofluo images registration

Usage:
------
    io_tif_to_tifs -i <path/image.tif> -t autofl [-v]
"""

from glob import glob
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import save_metadata_to_file, save_as_tifs, load_3D_tif
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image.tif (can use glob patterns)', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-t', '--tif_dir', help='Name of output folder for outputting tifs', required=True, action=SM)
    opts.add_argument('-m', '--metad_path', help='Path for storing key raw image metadata. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_paths = list(Path().cwd().glob(str(args.input)))

    for input_path in input_paths:
        print(f"\n    Processing {input_path}\n")

        # Load .tif image (highest res dataset) as ndarray and extract voxel sizes in microns
        if args.metad_path:
            img = load_3D_tif(input_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=args.metad_path)
        else:
            img = load_3D_tif(input_path, desired_axis_order="xyz", return_res=False)

        # Save 3D tif as tifs
        if args.tif_dir:
            tifs_output_path = Path(args.tif_dir)
        else:
            if '.ome.tif' in str(input_path):
                tifs_output_path = str(Path(input_path).name).replace('.ome.tif', '_tifs')
            elif '.tif' in str(input_path):
                tifs_output_path = str(Path(input_path).name).replace('.tif', '_tifs')
            else:
                tifs_output_path = 'tifs'
        save_as_tifs(img, tifs_output_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()