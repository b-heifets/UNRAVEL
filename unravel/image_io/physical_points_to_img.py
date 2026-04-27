#!/usr/bin/env python3

"""
Use ``physical_points_to_img`` or ``pp2i`` from UNRAVEL to convert physical-space point coordinates (e.g., coordinates in µm) into a 3D image using a reference image.

This is useful when point coordinates are given in physical units rather than voxel indices. For example, Allen CCF25 coordinates in µm can be converted to voxel coordinates by dividing by 25.

Input:
    - CSV with physical coordinate columns, e.g. x, y, z

Output:
    - 3D image where each voxel contains the number of points at that location

Note:
    - Coordinates are assumed to be in the same axis order as the output image:
        x -> axis 0
        y -> axis 1
        z -> axis 2
    - For Allen CCF25 AP/DV/ML coordinates matching a PIR CCF image:
        x = AP
        y = DV
        z = ML
    - Points outside the reference image bounds are skipped.

Usage:
------
    physical_points_to_img -i coordinates.csv -ri atlas_CCFv3_2020_25um.nii.gz -x x -y y -z z -s 25 -o units_CCF25.nii.gz 
"""

from pathlib import Path

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.image_io.points_to_img import points_to_img


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Input CSV with physical point coordinates.", required=True, action=SM)
    reqs.add_argument("-ri", "--ref_img", help="Reference image for output shape and NIfTI metadata.", required=True, action=SM)

    coord_args = parser.add_argument_group("Coordinate arguments")
    coord_args.add_argument("-x", "--x_col", help="Column for output image axis 0. Default: x", default="x", action=SM)
    coord_args.add_argument("-y", "--y_col", help="Column for output image axis 1. Default: y", default="y", action=SM)
    coord_args.add_argument("-z", "--z_col", help="Column for output image axis 2. Default: z", default="z", action=SM)
    coord_args.add_argument("-s", "--spacing", help="Physical spacing per voxel. Use one value for isotropic spacing or three values for x/y/z spacing, e.g. -s 25 or -s 25 25 25.", required=True, nargs="*", type=float, action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-o", "--output", help="Output image path. Default: input stem + .nii.gz", default=None, action=SM)
    opts.add_argument("-f", "--filter", help="Optional pandas query string for filtering rows before conversion. Example: -q \"recording_name == 'NP09_R1' and shank_id == 0\"", default=None, action=SM)
    opts.add_argument("-b", "--binary", help="Write binary occupancy instead of point counts. Default: False", action="store_true", default=False)
    opts.add_argument("--floor", help="Use floor(coord / spacing) instead of rounding. Default: False", action="store_true", default=False)
    opts.add_argument("-1", "--one-indexed", help=("Subtract 1 from voxel coordinates after conversion. Use only if input physical coordinates were derived from one-indexed voxel indices."), action="store_true", default=False)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def parse_spacing(spacing):
    """Return spacing as a length-3 numpy array."""
    if len(spacing) == 1:
        return np.array([spacing[0], spacing[0], spacing[0]], dtype=float)
    if len(spacing) == 3:
        return np.array(spacing, dtype=float)
    raise ValueError("Spacing must be one value or three values.")


def validate_columns(df, columns):
    """Raise a helpful error if required columns are missing."""
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required column(s): {missing}\n"
            f"Available columns: {list(df.columns)}"
        )


def physical_to_voxel_coords(points_df, x_col, y_col, z_col, spacing, use_floor=False, one_indexed=False):
    """Convert x/y/z physical point coordinates to voxel indices and return as a numpy array"""
    physical = points_df[[x_col, y_col, z_col]].to_numpy(dtype=float)

    voxel = physical / spacing

    if use_floor:
        voxel = np.floor(voxel)
    else:
        voxel = np.rint(voxel)

    voxel = voxel.astype(int)

    if one_indexed:
        voxel -= 1

    return voxel


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    ref_img_path = Path(args.ref_img)

    spacing = parse_spacing(args.spacing)

    points_df = pd.read_csv(input_path)

    if args.filter:
        if args.verbose:
            print(f"\n[blue]Filtering points using query:[/] {args.filter}")
            print(f"    Original points: {len(points_df)}")

        points_df = points_df.query(args.filter).copy()

        if args.verbose:
            print(f"    Remaining points: {len(points_df)}\n")

    validate_columns(points_df, [args.x_col, args.y_col, args.z_col])

    voxel_coords = physical_to_voxel_coords(
        points_df,
        x_col=args.x_col,
        y_col=args.y_col,
        z_col=args.z_col,
        spacing=spacing,
        use_floor=args.floor,
        one_indexed=args.one_indexed,
    )

    ref_img = load_3D_img(ref_img_path, verbose=args.verbose)

    img = points_to_img(voxel_coords, ref_img)

    if args.binary:
        img = (img > 0).astype(np.uint8)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / str(input_path.stem + ".nii.gz")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    save_3D_img(
        img,
        output_path=output_path,
        reference_img=ref_img_path,
        data_type=img.dtype,
        verbose=args.verbose,
    )

    print(f"    Output image saved to: {output_path}\n")

    if args.verbose:
        print(f"    Input points: {len(points_df)}")
        print(f"    Nonzero voxels: {np.count_nonzero(img)}")
        print(f"    Max voxel count: {np.max(img)}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()