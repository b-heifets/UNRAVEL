#!/usr/bin/env python3

"""
Use ``coords_points_to_labeled_voxel_img`` or ``points_to_labeled_voxel_img`` from UNRAVEL to convert point coordinates into a labeled unique-voxel image.

This is useful when many units/channels occupy the same voxel. Instead of
creating one image per unit, this script groups rows by voxel coordinate and
assigns one unique integer label per occupied voxel.

Input:
    - CSV with voxel coordinates, usually x, y, z from ``coords_physical_points_add_regions``
    - Reference image for output shape/header

Outputs:
    - labeled image where img[x, y, z] = voxel_label
    - mapping CSV linking voxel_label back to all rows/units/channels in that voxel
    - row-level mapping CSV preserving one row per original unit/channel

Notes:
    - Input coordinates must already be voxel/index coordinates.
    - If coordinates are physical coordinates, run ``coords_physical_points_add_regions``
      or ``coords_physical_points_to_img``-style conversion first.
    - Use nearest-neighbor/multiLabel interpolation when reorienting, resampling,
      or warping the output labeled image.
    - Aggregated columns in the mapping CSV (from ``-c``) are stored as
      sorted unique values and are NOT guaranteed to preserve row-wise alignment
      across columns (e.g., unit_id ↔ channel_id). Use the row-level mapping CSV
      for analyses requiring exact correspondence between columns.

Usage:
------
    points_to_labeled_voxel_img \\
        -i units_with_regions.csv \\
        -ri samples/downsampled_standard_NP09_488_Ch0.nii.gz \\
        -x x -y y -z z \\
        [-c recording_name unit_id channel_id shank_id abbreviation full_structure_name lowered_ID] \\
        -o unique_voxels \\
        -v
"""

from pathlib import Path

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import get_stem, log_command, verbose_start_msg, verbose_end_msg
from unravel.coordinates.physical_points_to_img import validate_columns


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Input CSV with voxel coordinates.", required=True, action=SM)
    reqs.add_argument("-ri", "--ref_img", help="Reference image for output shape/header.", required=True, action=SM)

    coord_args = parser.add_argument_group("Coordinate arguments")
    coord_args.add_argument("-x", "--x_col", help="Voxel coordinate column for axis 0. Default: x", default="x", action=SM)
    coord_args.add_argument("-y", "--y_col", help="Voxel coordinate column for axis 1. Default: y", default="y", action=SM)
    coord_args.add_argument("-z", "--z_col", help="Voxel coordinate column for axis 2. Default: z", default="z", action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-c", "--cols", help="Columns to aggregate into mapping CSV (IDs + metadata). For example: recording_name unit_id channel_id shank_id abbreviation full_structure_name lowered_ID", nargs="*", default=None, action=SM)
    opts.add_argument("-o", "--output", help="Output directory. Default: unique_voxels", default="unique_voxels", action=SM)
    opts.add_argument("-f", "--filter", help="Optional pandas query string.", default=None, action=SM)
    opts.add_argument("-p", "--prefix", help="Output filename prefix. Default: input stem", default=None, action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def aggregate_values(series):
    """Return sorted unique non-null values joined by semicolons."""
    vals = series.dropna().astype(str).unique().tolist()
    vals = sorted(vals)
    return ";".join(vals)


def choose_dtype(max_label):
    """Choose a reasonable integer dtype for the labeled image."""
    if max_label <= np.iinfo(np.uint16).max:
        return np.uint16
    return np.uint32


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    ref_img_path = Path(args.ref_img)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    prefix = args.prefix if args.prefix else get_stem(input_path)

    df = pd.read_csv(input_path)

    if args.filter:
        if args.verbose:
            print(f"\n[blue]Filtering rows using filter:[/] {args.filter}")
            print(f"    Original rows: {len(df)}")
        df = df.query(args.filter).copy()
        if args.verbose:
            print(f"    Remaining rows: {len(df)}\n")

    validate_columns(df, [args.x_col, args.y_col, args.z_col])

    ref_img = load_3D_img(ref_img_path, verbose=args.verbose)
    shape = ref_img.shape

    # Convert voxel coordinates to integer indices.
    df = df.copy()
    df["voxel_x"] = np.rint(df[args.x_col]).astype(int)
    df["voxel_y"] = np.rint(df[args.y_col]).astype(int)
    df["voxel_z"] = np.rint(df[args.z_col]).astype(int)

    in_bounds = (
        (df["voxel_x"] >= 0) & (df["voxel_x"] < shape[0]) &
        (df["voxel_y"] >= 0) & (df["voxel_y"] < shape[1]) &
        (df["voxel_z"] >= 0) & (df["voxel_z"] < shape[2])
    )

    n_out_of_bounds = int((~in_bounds).sum())
    df_valid = df[in_bounds].copy()

    if len(df_valid) == 0:
        raise ValueError("No valid in-bounds points were found.")

    # Assign one label per unique voxel.
    unique_voxels = (
        df_valid[["voxel_x", "voxel_y", "voxel_z"]]
        .drop_duplicates()
        .sort_values(["voxel_x", "voxel_y", "voxel_z"])
        .reset_index(drop=True)
    )
    unique_voxels["voxel_label"] = np.arange(1, len(unique_voxels) + 1, dtype=np.int64)

    df_valid = df_valid.merge(unique_voxels, on=["voxel_x", "voxel_y", "voxel_z"], how="left")

    dtype = choose_dtype(len(unique_voxels))
    img = np.zeros(shape, dtype=dtype)

    coords = unique_voxels[["voxel_x", "voxel_y", "voxel_z"]].to_numpy(dtype=int)
    labels = unique_voxels["voxel_label"].to_numpy(dtype=dtype)
    img[coords[:, 0], coords[:, 1], coords[:, 2]] = labels

    # Named aggregation is easier when constructed explicitly.
    grouped = df_valid.groupby("voxel_label", as_index=False)

    mapping_df = unique_voxels.copy()
    mapping_df["n_rows"] = mapping_df["voxel_label"].map(grouped.size().set_index("voxel_label")["size"])

    # Build a mapping CSV: one row per unique voxel.
    if args.cols is None:
        if args.verbose:
            print("[yellow]No --cols provided → skipping aggregated mapping columns[/]")
        agg_cols = []
    else:
        agg_cols = [col for col in args.cols if col in df_valid.columns]

    for col in agg_cols:
        mapping_df[col] = mapping_df["voxel_label"].map(grouped[col].agg(aggregate_values).set_index("voxel_label")[col])

    # Also save a row-level mapping so every original unit/channel can be recovered.
    row_mapping_cols = ["voxel_label", "voxel_x", "voxel_y", "voxel_z"] + [
        col for col in df_valid.columns
        if col not in ["voxel_label", "voxel_x", "voxel_y", "voxel_z"]
    ]
    row_mapping_df = df_valid[row_mapping_cols].copy()

    output_img_path = output_dir / f"{prefix}__labeled_unique_voxels.nii.gz"
    output_map_path = output_dir / f"{prefix}__unique_voxel_mapping.csv"
    output_rows_path = output_dir / f"{prefix}__row_to_unique_voxel_mapping.csv"

    # Convert numpy dtype to a string for nibabel. This is a bit hacky but ensures we get the correct integer type in the output NIfTI.
    if dtype == np.uint16:
        nii_dtype = "uint16"
    elif dtype == np.uint32:
        nii_dtype = "uint32"
    else:
        raise ValueError(f"Unsupported dtype: {dtype}")

    save_3D_img(
        img,
        output_path=output_img_path,
        reference_img=ref_img_path,
        data_type=nii_dtype,
        verbose=args.verbose,
    )

    mapping_df.to_csv(output_map_path, index=False)
    row_mapping_df.to_csv(output_rows_path, index=False)

    print(f"\n    Input rows: {len(df)}")
    print(f"    In-bounds rows: {len(df_valid)}")
    print(f"    Out-of-bounds rows skipped: {n_out_of_bounds}")
    print(f"    Unique occupied voxels: {len(unique_voxels)}")
    print(f"    Max voxel label: {len(unique_voxels)}")
    print(f"    Output image: {output_img_path}")
    print(f"    Unique voxel mapping CSV: {output_map_path}")
    print(f"    Row-to-voxel mapping CSV: {output_rows_path}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()