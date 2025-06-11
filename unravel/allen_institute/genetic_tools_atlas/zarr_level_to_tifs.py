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

import os
import zarr
import tifffile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from rich.traceback import install
from rich import print

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import save_metadata_to_file
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


# def save_pixel_spacing_txt(output_dir, spacing_xyz):
#     """Save voxel spacing in microns to a text file."""
#     spacing_txt = Path(output_dir) / "pixel_spacing.txt"
#     with open(spacing_txt, "w") as f:
#         f.write("Voxel size in microns (Z [depth], Y [height], X [width]):\n")
#         f.write(f"{spacing_xyz[0]} {spacing_xyz[1]} {spacing_xyz[2]}\n")


def save_slice_tif(slice_, slice_idx, out_dir):
    """Save a single TIFF slice."""
    slice_path = out_dir / f"slice_{slice_idx:04d}.tif"
    tifffile.imwrite(str(slice_path), slice_)

def save_as_tifs_parallel(ndarray, tif_dir_out):
    """Save 3D image as a TIFF series using parallel writing."""
    tif_dir_out = Path(tif_dir_out)
    tif_dir_out.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(save_slice_tif, slice_, i, tif_dir_out)
                   for i, slice_ in enumerate(ndarray)]
        for f in futures:
            f.result()  # Wait for all to finish

    print(f"✅ Saved TIFFs at {tif_dir_out}")

def zarr_level_to_tifs(zarr_path, output_dir, resolution_level, channel_map, xy_res=None, z_res=None):
    """
    Extracts a specified resolution level from a Zarr file and saves the specified channels as TIFF files.

    Parameters:
    -----------
    zarr_path : str or Path
        Path to the Zarr file.
    output_dir : str or Path
        Directory to save the output TIFF files. If None, defaults to "TIFFs/<sample_name>".
    resolution_level : str
        Resolution level to extract (e.g., "0", "1", ..., "9").
    channel_map : dict
        Mapping of output directory names to Zarr channel indices (e.g., {'red': 0, 'green': 1}).
    xy_res : float, optional
        X/Y resolution in microns.
    z_res : float, optional
        Z resolution in microns. Default is 100 µm for Genetic Tools Atlas data.
    """

    if not zarr_path.is_dir():
        raise NotADirectoryError(f"Zarr input path is not a directory: {zarr_path}")
    if not (zarr_path / resolution_level).is_dir():
        raise FileNotFoundError(f"Resolution level {resolution_level} not found in Zarr file: {zarr_path}")

    z = zarr.open(zarr_path, mode="r")
    z_level = z[resolution_level]

    if z_level.ndim != 4:
        raise ValueError(f"Expected shape (c, z, y, x), got {z_level.shape}")

    num_channels = z_level.shape[0]
    if num_channels == 1:
        print(f"⚠️ Only one channel found in {zarr_path.name}")

    print(f"📂 Processing {zarr_path.name} at resolution level {resolution_level}...")

    for name, idx in channel_map.items():
        out_dir = output_dir / name
        tif_files = list(out_dir.glob("*.tif"))
        if tif_files:
            print(f"⚠️ Skipping {name} in {zarr_path.name}: output TIFFs already exist at {out_dir}")
            continue
        if idx >= num_channels:
            print(f"⚠️ Channel index {idx} not found in {zarr_path.name} (only {num_channels} channels). Skipping {name}.")
            continue
        save_as_tifs_parallel(z_level[idx], out_dir)
        save_metadata_to_file(
            xy_res=xy_res, 
            z_res=z_res, 
            x_dim=z_level[idx].shape[2], 
            y_dim=z_level[idx].shape[1], 
            z_dim=z_level[idx].shape[0], 
            save_metadata=Path(out_dir).parent / "parameters" / "metadata.txt"
        )


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
