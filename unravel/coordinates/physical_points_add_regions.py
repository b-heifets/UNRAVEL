#!/usr/bin/env python3

"""
Use ``coords_physical_points_add_regions`` or ``ppar`` from UNRAVEL to add atlas region IDs and region metadata to a CSV containing physical-space point coordinates.

This is useful when point coordinates are in physical units, e.g. µm, rather
than voxel/index space. Coordinates are converted to voxel indices using the
provided spacing, then atlas IDs are looked up directly from an atlas image.

Input:
    - CSV with physical coordinate columns, e.g. channel_ml, channel_dv, channel_ap
    - Atlas image in the same array orientation as the coordinate columns
    - Region info CSV, e.g. CCFv3-2020_info.csv

Output:
    - CSV with original metadata plus:
        x, y, z
        Region_ID
        atlas_lookup_status
        abbreviation
        full_structure_name

Note:
    - Coordinates are assumed to be in the same axis order as the atlas image:
        x -> atlas axis 0
        y -> atlas axis 1
        z -> atlas axis 2
    - For Kevin's CCF-space images, this appeared to work:
        x = channel_ml
        y = channel_dv
        z = channel_ap
    - Points outside atlas bounds are retained but assigned Region_ID = 0.

Usage:
------
    coords_physical_points_add_regions \\
        -i ISOTRP_all_recordings_units_CCFcoordinates.csv \\
        -a CCF25/atlas_CCFv3_2020_25um_in_kevin_space.nii.gz \\
        -x channel_ml -y channel_dv -z channel_ap \\
        -s 25 \\
        -csv CCFv3-2020_info.csv \\
        -id lowered_ID \\
        -o units_with_regions.csv

Usage example for one recording:
--------------------------
    coords_physical_points_add_regions \\
        -i ISOTRP_all_recordings_units_CCFcoordinates.csv \\
        -a CCF25/atlas_CCFv3_2020_25um_in_kevin_space.nii.gz \\
        -x channel_ml -y channel_dv -z channel_ap \\
        -s 25 \\
        -f "recording_name == 'NP09_R1'" \\
        -csv CCFv3-2020_info.csv \\
        -id lowered_ID \\
        -o NP09_R1_units_with_regions.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.coordinates.physical_points_to_img import parse_spacing, physical_to_voxel_coords, validate_columns


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Input CSV with physical point coordinates.", required=True, action=SM)
    reqs.add_argument("-a", "--atlas", help="Atlas image matching the coordinate space/orientation.", required=True, action=SM)

    coord_args = parser.add_argument_group("Coordinate arguments")
    coord_args.add_argument("-x", "--x_col", help="Column for atlas axis 0. Default: x", default="x", action=SM)
    coord_args.add_argument("-y", "--y_col", help="Column for atlas axis 1. Default: y", default="y", action=SM)
    coord_args.add_argument("-z", "--z_col", help="Column for atlas axis 2. Default: z", default="z", action=SM)
    coord_args.add_argument("-s", "--spacing",help="Physical spacing per voxel. Use one value for isotropic spacing or three values for x/y/z spacing.", required=True, nargs="*", type=float,action=SM)

    region_args = parser.add_argument_group("Region info CSV arguments")
    region_args.add_argument('-rc', '--region_csv', help='CSV name or path/name.csv. Default: CCFv3-2020_info.csv', default='CCFv3-2020_info.csv', action=SM)
    region_args.add_argument('-rcc', '--region_csv_cols', help='Columns to load from the region CSV. Default: columns from -id, -abbr, -name', default=None, nargs='*', action=SM)
    region_args.add_argument("-id", "--region_id_col", help="Region ID column in region CSV. Default: lowered_ID", default="lowered_ID", action=SM)
    region_args.add_argument("-abbr", "--abbr_col", help="Abbreviation column in region CSV. Default: abbreviation", default="abbreviation", action=SM)
    region_args.add_argument("-name", "--name_col", help="Region name column in region CSV. Default: full_structure_name", default="full_structure_name", action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-o", "--output", help="Output CSV path. Default: input stem + _with_regions.csv", default=None, action=SM)
    opts.add_argument("-f", "--filter",help="Optional pandas query string. Example: -f \"recording_name == 'NP09_R1' and shank_id == 0\"",default=None,action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def lookup_region_ids(atlas_img, voxel_coords):
    shape = atlas_img.shape
    valid = (
        (voxel_coords[:, 0] >= 0) & (voxel_coords[:, 0] < shape[0]) &
        (voxel_coords[:, 1] >= 0) & (voxel_coords[:, 1] < shape[1]) &
        (voxel_coords[:, 2] >= 0) & (voxel_coords[:, 2] < shape[2])
    )

    valid_coords = voxel_coords[valid]
    region_ids = np.zeros(len(voxel_coords), dtype=np.int64)

    # For valid coordinates, look up region IDs from the atlas image. Out-of-bounds coordinates will retain a region ID of 0.
    region_ids[valid] = atlas_img[
        valid_coords[:, 0],
        valid_coords[:, 1],
        valid_coords[:, 2],
    ].astype(np.int64)

    # Create a status array to indicate whether each point was successfully looked up, out of bounds, or in the atlas but with Region_ID = 0
    status = np.full(len(voxel_coords), "out_of_bounds", dtype=object)
    status[valid] = "ok"
    status[valid & (region_ids == 0)] = "atlas_zero"

    return region_ids, status


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    atlas_path = Path(args.atlas)

    spacing = parse_spacing(args.spacing)

    points_df = pd.read_csv(input_path)

    if args.filter:
        if args.verbose:
            print(f"\n[blue]Filtering points using filter:[/] {args.filter}")
            print(f"    Original rows: {len(points_df)}")
        points_df = points_df.query(args.filter).copy()
        if args.verbose:
            print(f"    Remaining rows: {len(points_df)}\n")

    validate_columns(points_df, [args.x_col, args.y_col, args.z_col])

    voxel_coords = physical_to_voxel_coords(
        points_df,
        x_col=args.x_col,
        y_col=args.y_col,
        z_col=args.z_col,
        spacing=spacing
    )

    # Create output DataFrame with original metadata plus new columns for voxel coordinates and region info
    out_df = points_df.copy()
    out_df["x"] = voxel_coords[:, 0]
    out_df["y"] = voxel_coords[:, 1]
    out_df["z"] = voxel_coords[:, 2]

    atlas_img = load_3D_img(atlas_path, verbose=args.verbose)

    region_ids, status = lookup_region_ids(atlas_img, voxel_coords)
    out_df[args.region_id_col] = region_ids
    out_df["atlas_lookup_status"] = status

    # Load the specified columns from the CSV with CCFv3 info
    if args.region_csv_cols is None:
        columns_to_load = [args.region_id_col, args.abbr_col, args.name_col]
    else:
        columns_to_load = args.region_csv_cols
    if args.region_csv == 'CCFv3-2017_info.csv' or args.region_csv == 'CCFv3-2020_info.csv': 
        region_info_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.region_csv, usecols=columns_to_load)
    else:
        region_info_df = pd.read_csv(args.region_csv, usecols=columns_to_load)

    # Ensure region_ID is numeric for merging
    region_info_df = region_info_df.dropna(subset=[args.region_id_col])
    region_info_df[args.region_id_col] = region_info_df[args.region_id_col].astype(np.int64)

    out_df = out_df.merge(region_info_df, on=args.region_id_col, how="left")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + "_with_regions.csv")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)

    print(f"\n    Input rows: {len(points_df)}")
    print(f"    Atlas shape: {atlas_img.shape}")
    print(f"    Nonzero {args.region_id_col} rows: {(out_df[args.region_id_col] != 0).sum()}")
    print(f"    Out-of-bounds rows: {(out_df['atlas_lookup_status'] == 'out_of_bounds').sum()}")
    print(f"    Atlas-zero rows: {(out_df['atlas_lookup_status'] == 'atlas_zero').sum()}")
    print(f"    Output CSV saved to: {output_path}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()