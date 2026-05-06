#!/usr/bin/env python3

"""
Use ``points_to_sphere_masks`` to create one binary sphere/ellipsoid mask per
point in a CSV.

This is useful for generating local-neighborhood masks around transformed
coordinates, e.g. MERFISH-space unit locations.

Input:
    - CSV with voxel coordinate columns
    - Reference image for output shape/header

Output:
    - One .nii.gz binary mask per input row

Note:
    - Radius and voxel size must be in the same physical units, usually µm.
    - Coordinates are voxel/index coordinates, not physical coordinates.
    - For MERFISH-CCF, voxel size is often 10 10 200 µm.    

Usage:
------
    points_to_sphere_masks \\
        -i points_MERFISH.csv \\
        -ri resampled_annotation.nii.gz \\
        -x merfish_x -y merfish_y -z merfish_z \\
        -id voxel_label \\
        -r 100 \\
        -vx 10 10 200 \\
        -o unit_sphere_masks_MERFISH \\
        -v
"""

from pathlib import Path
import re

import numpy as np
import pandas as pd
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import initialize_progress_bar, log_command, verbose_start_msg, verbose_end_msg
from unravel.coordinates.physical_points_to_img import validate_columns


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Input CSV with voxel coordinates.", required=True, action=SM)
    reqs.add_argument("-ri", "--ref_img", help="Reference image for output shape/header.", required=True, action=SM)
    reqs.add_argument("-r", "--radius", help="Sphere radius in physical units, e.g. µm.", required=True, type=float, action=SM)

    coord_args = parser.add_argument_group("Coordinate arguments")
    coord_args.add_argument("-x", "--x_col", help="Voxel coordinate column for axis 0. Default: x", default="x", action=SM)
    coord_args.add_argument("-y", "--y_col", help="Voxel coordinate column for axis 1. Default: y", default="y", action=SM)
    coord_args.add_argument("-z", "--z_col", help="Voxel coordinate column for axis 2. Default: z", default="z", action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument(
        "-vx", "--voxel_size",
        help="Voxel size in physical units as x y z. Use one value for isotropic. Default: 1 1 1",
        default=[1, 1, 1],
        nargs="+",
        type=float,
        action=SM,
    )
    opts.add_argument(
        "-id", "--id_col",
        help="Column used to name each mask. Default: row_index",
        default=None,
        action=SM,
    )
    opts.add_argument(
        "-name", "--name_cols",
        help="Optional additional columns to include in filenames.",
        nargs="*",
        default=None,
        action=SM,
    )
    opts.add_argument(
        "-f", "--filter",
        help="Optional pandas query string for filtering rows before mask creation.",
        default=None,
        action=SM,
    )
    opts.add_argument(
        "--in-bounds-col",
        help="Optional boolean column used to keep only in-bounds rows, e.g. merfish_in_bounds.",
        default=None,
        action=SM,
    )
    opts.add_argument(
        "-o", "--output",
        help="Output directory. Default: sphere_masks",
        default="sphere_masks",
        action=SM,
    )
    opts.add_argument(
        "--skip-existing",
        help="Skip masks that already exist. Default: False",
        action="store_true",
        default=False,
    )

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def parse_voxel_size(voxel_size):
    """Return voxel size as a length-3 numpy array."""
    if len(voxel_size) == 1:
        return np.array([voxel_size[0], voxel_size[0], voxel_size[0]], dtype=float)
    if len(voxel_size) == 3:
        return np.array(voxel_size, dtype=float)
    raise ValueError("Voxel size must be one value or three values.")


def sanitize_filename(text):
    """Make a safe filename component."""
    text = str(text)
    text = text.replace(" ", "-")
    text = re.sub(r"[^A-Za-z0-9_.=-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def make_mask_name(row, row_index, id_col=None, name_cols=None, radius=None):
    """Create a filename stem for one point/mask."""
    parts = []

    if id_col is not None and id_col in row.index and pd.notna(row[id_col]):
        parts.append(f"{id_col}-{sanitize_filename(row[id_col])}")
    else:
        parts.append(f"row-{row_index}")

    if name_cols:
        for col in name_cols:
            if col in row.index and pd.notna(row[col]):
                parts.append(f"{col}-{sanitize_filename(row[col])}")

    if radius is not None:
        parts.append(f"r{radius:g}")

    return "__".join(parts)


def sphere_mask_for_coord(shape, center, radius, voxel_size):
    """Create a binary physical-radius sphere/ellipsoid mask around a voxel coordinate."""
    center = np.array(center, dtype=float)
    voxel_size = np.array(voxel_size, dtype=float)

    radius_vox = np.ceil(radius / voxel_size).astype(int)

    x, y, z = np.rint(center).astype(int)

    x0, x1 = max(0, x - radius_vox[0]), min(shape[0], x + radius_vox[0] + 1)
    y0, y1 = max(0, y - radius_vox[1]), min(shape[1], y + radius_vox[1] + 1)
    z0, z1 = max(0, z - radius_vox[2]), min(shape[2], z + radius_vox[2] + 1)

    xs = np.arange(x0, x1)
    ys = np.arange(y0, y1)
    zs = np.arange(z0, z1)

    xx, yy, zz = np.meshgrid(xs, ys, zs, indexing="ij")
    coords = np.stack([xx, yy, zz], axis=-1).astype(float)

    distances = np.sqrt(np.sum(((coords - center) * voxel_size) ** 2, axis=-1))

    mask = np.zeros(shape, dtype=np.uint8)
    mask[x0:x1, y0:y1, z0:z1] = (distances <= radius).astype(np.uint8)

    return mask


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

    voxel_size = parse_voxel_size(args.voxel_size)

    df = pd.read_csv(input_path)

    if args.filter:
        if args.verbose:
            print(f"\n[blue]Filtering rows using filter:[/] {args.filter}")
            print(f"    Original rows: {len(df)}")
        df = df.query(args.filter).copy()
        if args.verbose:
            print(f"    Remaining rows: {len(df)}\n")

    if args.in_bounds_col:
        validate_columns(df, [args.in_bounds_col])
        before = len(df)
        df = df[df[args.in_bounds_col].astype(bool)].copy()
        if args.verbose:
            print(f"    Kept in-bounds rows: {len(df)} / {before}")

    validate_columns(df, [args.x_col, args.y_col, args.z_col])

    ref_img = load_3D_img(ref_img_path, verbose=args.verbose)
    shape = ref_img.shape

    progress, task_id = initialize_progress_bar(len(df), task_message="[bold green]Creating sphere masks...")

    n_written = 0
    n_skipped_existing = 0
    n_out_of_bounds = 0

    with Live(progress):
        for row_index, row in df.iterrows():
            coord = np.array([row[args.x_col], row[args.y_col], row[args.z_col]], dtype=float)
            rounded = np.rint(coord).astype(int)

            if not (
                0 <= rounded[0] < shape[0] and
                0 <= rounded[1] < shape[1] and
                0 <= rounded[2] < shape[2]
            ):
                n_out_of_bounds += 1
                progress.update(task_id, advance=1)
                continue

            stem = make_mask_name(
                row,
                row_index=row_index,
                id_col=args.id_col,
                name_cols=args.name_cols,
                radius=args.radius,
            )
            output_path = output_dir / f"{stem}.nii.gz"

            if args.skip_existing and output_path.exists():
                n_skipped_existing += 1
                progress.update(task_id, advance=1)
                continue

            mask = sphere_mask_for_coord(
                shape=shape,
                center=coord,
                radius=args.radius,
                voxel_size=voxel_size,
            )

            save_3D_img(
                mask,
                output_path=output_path,
                reference_img=ref_img_path,
                data_type="uint8",
                verbose=False,
            )

            n_written += 1
            progress.update(task_id, advance=1)

    print(f"\n    Input rows after filtering: {len(df)}")
    print(f"    Masks written: {n_written}")
    print(f"    Skipped existing: {n_skipped_existing}")
    print(f"    Out-of-bounds rows skipped: {n_out_of_bounds}")
    print(f"    Radius: {args.radius:g}")
    print(f"    Voxel size: {voxel_size.tolist()}")
    print(f"    Output directory: {output_dir}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()