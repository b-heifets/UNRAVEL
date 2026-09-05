#!/usr/bin/env python3

"""
Use ``io_czi_subset`` (``czi_subset``) from UNRAVEL to read a padded 3D
subregion from one CZI channel and save it as a TIFF series.

The bounds are voxel indices in the ``xyz`` coordinate system used by
``load_3D_img()`` and ``img_max_projection``. Bounds follow normal Python
half-open slicing: minima are included and maxima are excluded.

Inputs:
    - A .czi image.
    - Six bounds: xmin xmax ymin ymax zmin zmax.

Outputs:
    - A TIFF series named slice_0000.tif, slice_0001.tif, ...
    - subset_bounds.json containing the original bounds, applied padding,
      clamped bounds, source dimensions, and CZI coordinates.

Notes:
    - Padding is specified in voxels as one value for all axes or three values
      for x, y, and z. Padded bounds are clamped to the source image.
    - Only the requested XY region and Z planes are read from the CZI. The
      complete 3D image is not loaded into memory.
    - Existing slice_*.tif files cause the sample to be skipped unless
      ``--force`` is used.
    - ``--bounds`` is applied to every sample selected with ``--dirs``. Process
      samples separately unless the same coordinates are valid for all of them.

Usage:
------
    czi_subset -i '*.czi' -b xmin xmax ymin ymax zmin zmax \
        [-pad 50] [-o brain_tifs] [-c 0] [-s 0] [-f] [-n] [-v]

Examples:
---------
    czi_subset -i '*.czi' -c 0 -b 150 4200 90 3000 20 680 -pad 50
    czi_subset -i '*.czi' -c 1 -b 150 4200 90 3000 20 680 \
        -pad 50 50 25 -o brain_c1
    czi_subset -i '*.czi' -b 150 4200 90 3000 20 680 -pad 50 -n
"""

import json
from pathlib import Path

import numpy as np
import tifffile
from aicspylibczi import CziFile
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import extract_resolution
from unravel.core.utils import (
    get_samples,
    initialize_progress_bar,
    log_command,
    print_func_name_args_times,
    verbose_end_msg,
    verbose_start_msg,
)


def parse_args():
    parser = RichArgumentParser(
        formatter_class=SuppressMetavar,
        add_help=False,
        docstring=__doc__,
    )

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument(
        "-i",
        "--input",
        help=(
            "CZI path relative to each sample directory or glob pattern "
            "(e.g., '*.czi'). First match used."
        ),
        required=True,
        action=SM,
    )
    reqs.add_argument(
        "-b",
        "--bounds",
        help=(
            "Unpadded half-open bounds in xyz order: "
            "xmin xmax ymin ymax zmin zmax."
        ),
        required=True,
        nargs=6,
        type=int,
        action=SM,
    )

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument(
        "-pad",
        "--padding",
        help=(
            "Padding in voxels: one value for xyz or three values for x y z. "
            "Default: 0"
        ),
        nargs="+",
        type=int,
        default=[0],
        action=SM,
    )
    opts.add_argument(
        "-o",
        "--output",
        help="Output directory relative to each sample directory. Default: brain_tifs",
        default="brain_tifs",
        action=SM,
    )
    opts.add_argument(
        "-c",
        "--channel",
        help="CZI channel number. Default: 0",
        default=0,
        type=int,
        action=SM,
    )
    opts.add_argument(
        "-s",
        "--scene",
        help="CZI scene number. Default: 0",
        default=0,
        type=int,
        action=SM,
    )
    opts.add_argument(
        "-f",
        "--force",
        help="Replace existing slice_*.tif files and subset_bounds.json.",
        action="store_true",
        default=False,
    )
    opts.add_argument(
        "-n",
        "--dry_run",
        help="Validate and print the padded bounds without reading pixel data.",
        action="store_true",
        default=False,
    )

    general = parser.add_argument_group("General arguments")
    general.add_argument(
        "-d",
        "--dirs",
        help=(
            "Paths to sample directories and/or directories containing them "
            "(space-separated) for batch processing. Default: current dir"
        ),
        nargs="*",
        default=None,
        action=SM,
    )
    general.add_argument(
        "-p",
        "--pattern",
        help="Pattern for directories to process. Default: sample??",
        default="sample??",
        action=SM,
    )
    general.add_argument(
        "-v",
        "--verbose",
        help="Increase verbosity. Default: False",
        action="store_true",
        default=False,
    )

    return parser.parse_args()


def resolve_czi_path(sample_path, path_or_pattern):
    """Resolve an absolute CZI path or the first match within a sample."""
    path_or_pattern = Path(path_or_pattern)

    if path_or_pattern.is_absolute():
        return path_or_pattern if path_or_pattern.exists() else None

    return next(sample_path.glob(str(path_or_pattern)), None)


def normalize_padding(padding):
    """Return padding as a nonnegative ``(x, y, z)`` tuple."""
    if len(padding) == 1:
        padding = padding * 3
    elif len(padding) != 3:
        raise ValueError("--padding requires one value or three values: x y z.")

    if any(value < 0 for value in padding):
        raise ValueError("--padding values must be zero or greater.")

    return tuple(padding)


def validate_and_pad_bounds(bounds, shape_xyz, padding):
    """Validate half-open bounds, add padding, and clamp to ``shape_xyz``."""
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    x_size, y_size, z_size = shape_xyz
    x_pad, y_pad, z_pad = normalize_padding(padding)

    for axis, minimum, maximum, size in (
        ("x", xmin, xmax, x_size),
        ("y", ymin, ymax, y_size),
        ("z", zmin, zmax, z_size),
    ):
        if minimum < 0 or maximum > size or minimum >= maximum:
            raise ValueError(
                f"Invalid {axis} bounds {minimum}:{maximum} for size {size}. "
                "Bounds are half-open and must satisfy 0 <= min < max <= size."
            )

    padded_bounds = (
        max(0, xmin - x_pad),
        min(x_size, xmax + x_pad),
        max(0, ymin - y_pad),
        min(y_size, ymax + y_pad),
        max(0, zmin - z_pad),
        min(z_size, zmax + z_pad),
    )
    return padded_bounds, (x_pad, y_pad, z_pad)


def select_dim_shape(czi, scene):
    """Select the dimension dictionary containing ``scene``."""
    dim_shapes = czi.get_dims_shape()

    for dim_shape in dim_shapes:
        scene_start, scene_size = dim_shape.get("S", (0, 1))
        if scene_start <= scene < scene_start + scene_size:
            return dim_shape

    raise ValueError(f"Scene {scene} was not found in the CZI dimensions.")


def czi_geometry(czi, channel=0, scene=0):
    """Return array dimensions and the absolute CZI XY/Z origins."""
    dim_shape = select_dim_shape(czi, scene)
    z_start, z_size = dim_shape.get("Z", (0, 1))
    channel_start, channel_size = dim_shape.get("C", (0, 1))

    if not channel_start <= channel < channel_start + channel_size:
        raise ValueError(
            f"Channel {channel} is outside the CZI channel range "
            f"{channel_start}:{channel_start + channel_size}."
        )

    if czi.is_mosaic():
        bbox = czi.get_mosaic_bounding_box()
    else:
        bbox = czi.get_scene_bounding_box(scene)

    shape_xyz = (bbox.w, bbox.h, z_size)
    origin_xyz = (bbox.x, bbox.y, z_start)
    return shape_xyz, origin_xyz


def read_czi_plane(czi, channel, scene, z_coordinate, region):
    """Read one cropped CZI plane and return it as a ``yx`` ndarray."""
    kwargs = {"C": channel, "Z": z_coordinate}

    if czi.is_mosaic():
        plane = czi.read_mosaic(
            region=region,
            scale_factor=1.0,
            **kwargs,
        )
    else:
        if "S" in czi.dims:
            kwargs["S"] = scene
        plane = czi.read_image(region=region, **kwargs)[0]

    plane = np.squeeze(plane)
    if plane.ndim != 2:
        raise ValueError(
            f"Expected one 2D grayscale plane; received shape {plane.shape}. "
            "Check whether the CZI has additional non-singleton dimensions."
        )
    return plane


def clear_previous_outputs(output_dir):
    """Remove only files owned by this exporter from ``output_dir``."""
    for tif_path in output_dir.glob("slice_*.tif"):
        tif_path.unlink()

    metadata_path = output_dir / "subset_bounds.json"
    if metadata_path.exists():
        metadata_path.unlink()


@print_func_name_args_times()
def export_czi_subset(
    czi_path,
    output_dir,
    bounds,
    padding=(0,),
    channel=0,
    scene=0,
    force=False,
    dry_run=False,
):
    """Read a padded CZI bounding box one Z plane at a time and save TIFFs."""
    czi_path = Path(czi_path)
    output_dir = Path(output_dir)

    if czi_path.suffix.lower() != ".czi":
        raise ValueError(f"Input must be a .czi file: {czi_path}")

    existing_tifs = list(output_dir.glob("slice_*.tif")) if output_dir.exists() else []
    if existing_tifs and not force and not dry_run:
        print(f"\n    TIFF series already exists in {output_dir}. Skipping.")
        return None

    czi = CziFile(czi_path)
    shape_xyz, origin_xyz = czi_geometry(czi, channel=channel, scene=scene)
    padded_bounds, padding_xyz = validate_and_pad_bounds(
        tuple(bounds),
        shape_xyz,
        tuple(padding),
    )

    xmin, xmax, ymin, ymax, zmin, zmax = padded_bounds
    x_origin, y_origin, z_origin = origin_xyz
    subset_shape_xyz = (xmax - xmin, ymax - ymin, zmax - zmin)
    czi_region_xy = (
        x_origin + xmin,
        y_origin + ymin,
        xmax - xmin,
        ymax - ymin,
    )

    print(f"\n    Input: {czi_path}")
    print(f"    Source shape (xyz): {shape_xyz}")
    print(f"    Unpadded bounds: {tuple(bounds)}")
    print(f"    Padding (xyz): {padding_xyz}")
    print(f"    Padded bounds: {padded_bounds}")
    print(f"    Output shape (xyz): {subset_shape_xyz}")

    if dry_run:
        return {
            "source_shape_xyz": shape_xyz,
            "unpadded_bounds_xyz": tuple(bounds),
            "padding_xyz": padding_xyz,
            "padded_bounds_xyz": padded_bounds,
            "subset_shape_xyz": subset_shape_xyz,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    if force:
        clear_previous_outputs(output_dir)

    output_dtype = None
    for output_z, source_z in enumerate(range(zmin, zmax)):
        plane = read_czi_plane(
            czi,
            channel=channel,
            scene=scene,
            z_coordinate=z_origin + source_z,
            region=czi_region_xy,
        )
        output_dtype = str(plane.dtype)
        tifffile.imwrite(output_dir / f"slice_{output_z:04d}.tif", plane)

        if Configuration.verbose and (output_z + 1) % 100 == 0:
            print(f"    Saved {output_z + 1}/{subset_shape_xyz[2]} slices")

    xy_res, z_res = extract_resolution(czi_path)
    metadata = {
        "input": str(czi_path.resolve()),
        "channel": channel,
        "scene": scene,
        "source_shape_xyz": shape_xyz,
        "source_czi_origin_xyz": origin_xyz,
        "unpadded_bounds_xyz": tuple(bounds),
        "padding_xyz_voxels": padding_xyz,
        "padded_bounds_xyz": padded_bounds,
        "subset_shape_xyz": subset_shape_xyz,
        "czi_region_xy": czi_region_xy,
        "czi_z_range": (z_origin + zmin, z_origin + zmax),
        "xy_resolution_um": xy_res,
        "z_resolution_um": z_res,
        "dtype": output_dtype,
        "bounds_convention": "half-open: minima included, maxima excluded",
        "tiff_axis_order": "series z; TIFF rows y; TIFF columns x",
    }
    with open(output_dir / "subset_bounds.json", "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)
        file.write("\n")

    print(f"    Output: [default bold]{output_dir}")
    return metadata


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)
    progress, task_id = initialize_progress_bar(
        len(sample_paths),
        "[red]Exporting CZI subsets...",
    )

    with Live(progress):
        for sample_path in sample_paths:
            sample_path = Path(sample_path)
            czi_path = resolve_czi_path(sample_path, args.input)

            if czi_path is None:
                print(
                    f"\n    [red1]No files match the path or pattern "
                    f"{args.input} in {sample_path}\n"
                )
                progress.update(task_id, advance=1)
                continue

            export_czi_subset(
                czi_path=czi_path,
                output_dir=sample_path / args.output,
                bounds=args.bounds,
                padding=args.padding,
                channel=args.channel,
                scene=args.scene,
                force=args.force,
                dry_run=args.dry_run,
            )
            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == "__main__":
    main()
