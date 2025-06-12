#!/usr/bin/env python3

"""
Convert a Zarr file to a series of TIFF files (e.g., for Ilastik segmentation).

Outputs:
    - Saves specified channels as TIFFs in separate directories in the output directory.
    - Saves pixel spacing in microns to output_dir/parameters/metadata.txt.

Note:
    - Genetic Tools Atlas Zarr levels and X/Y resolutions:
        - 0: 0.35 µm
        - 1: 0.7 µm
        - 2: 1.4 µm
        - 3: 2.8 µm (recommended for segmentation of GTA data)
        - 4: 5.6 µm
        - 5: 11.2 µm
        - 6: 22.4 µm
        - 7: 44.8 µm
        - 8: 89.6 µm
        - 9: 179.2 µm
    - Z resolution is always 100 µm.

Usage:
------
    ./zarr_level_to_tifs.py -i '<asterisk>.zarr' --channel-map red:0 green:1 [-l 3] [-o TIFFs/sample_name] [-v]
"""

from pathlib import Path
from rich.traceback import install
from rich import print

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import zarr_level_to_tifs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Glob pattern to match Zarr files to process (e.g., '*.zarr')", required=True, action=SM)
    reqs.add_argument('-c', '--channel-map', help="Mapping of output directory names to Zarr channel indices (e.g., red:0 green:1).", nargs='*', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-l', '--level', help='Resolution level to extract. Default: 3', required=True, choices=[str(i) for i in range(10)], default=3, action=SM)
    opts.add_argument('-s', '--spacing', help="Override voxel spacing in microns as a comma-separated string (z,y,x), e.g. '100.0,2.8,2.8'.", default=None, action=SM)

    opts.add_argument('-x', '--xy_res', help='xy resolution in um (overrides GTA spacing)', type=float, default=None, action=SM)
    opts.add_argument('-z', '--z_res', help='z resolution in um (overrides GTA spacing)', type=float, default=None, action=SM)
    opts.add_argument('-o', '--output', help='Output directory for TIFF files. Default: TIFFs/<Zarr name before the extension>', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Resolutions from the Genetic Tools Atlas Zarr files
    spacing_dict = {
        "0": (0.35, 0.35, 100.0),
        "1": (0.7, 0.7, 100.0),
        "2": (1.4, 1.4, 100.0),
        "3": (2.8, 2.8, 100.0),
        "4": (5.6, 5.6, 100.0),
        "5": (11.2, 11.2, 100.0),
        "6": (22.4, 22.4, 100.0),
        "7": (44.8, 44.8, 100.0),
        "8": (89.6, 89.6, 100.0),
        "9": (179.2, 179.2, 100.0)
    }

    # Determine the resolution
    xy_res = args.xy_res if args.xy_res is not None else spacing_dict[args.level][0] if args.level in spacing_dict else None
    z_res = args.z_res if args.z_res is not None else 100.0  # Default Z resolution is 100 µm
    if xy_res is None:
        raise ValueError("xy resolution must be provided either via --xy_res or the Genetic Tools Atlas spacing dictionary.")
    print(f"Using xy resolution: {xy_res} µm, z resolution: {z_res} µm")

    try:
        channel_map = {}
        for item in args.channel_map:
            name, idx = item.split(":")
            channel_map[name] = int(idx)
    except Exception as e:
        raise ValueError(f"Invalid format in --channel-map '{item}': must be NAME:INDEX (e.g., red:0)") from e

    zarr_files = zarr_files = list(Path().glob(args.input))
    if not zarr_files:
        raise FileNotFoundError(f"No Zarr files found matching pattern: {args.input}")

    for zarr_file in zarr_files:

        output_dir = Path(args.output) if args.output else Path("TIFFs") / zarr_file.stem

        zarr_level_to_tifs(
            zarr_path=zarr_file,
            output_dir=output_dir,
            resolution_level=args.level,
            channel_map=channel_map,
            xy_res=xy_res,
            z_res=z_res,
        )

    verbose_end_msg()


if __name__ == '__main__':
    main()
