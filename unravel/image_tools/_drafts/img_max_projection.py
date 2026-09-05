#!/usr/bin/env python3

"""
Use ``img_max_projection`` (``img_mip``) from UNRAVEL to create maximum
intensity projections (MIPs) of a 3D image along the x, y, and z axes.

Inputs:
    - 3D image: .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

Outputs:
    - Three 2D TIFF files in one output directory:
        - mip_x.tif: x-axis projection (yz view)
        - mip_y.tif: y-axis projection (xz view)
        - mip_z.tif: z-axis projection (xy view)

Notes:
    - The axis in each filename is the axis collapsed by the maximum operation.
    - ``load_3D_img()`` loads the selected .czi or .zarr channel. For other
      input formats, ``--channel`` has no effect.
    - The input dtype is preserved in the output TIFF files.
    - Existing output files are skipped unless ``--overwrite`` is used.

Usage:
------
    img_max_projection -i <image_or_glob> [-o mip] [-c 0] [-d <dirs>] [-p sample??] [-ow] [-v]

Examples:
---------
    img_max_projection -i '*.czi' -c 1
    img_max_projection -i full_res.tif -o mip
    img_max_projection -i '*.czi' -c 1 -d study1 study2 -p 'sample??'
"""

from pathlib import Path

import numpy as np
import tifffile
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img
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
            "Path to a 3D image (relative to each sample directory) or glob "
            "pattern (e.g., '*.czi'). First match used."
        ),
        required=True,
        action=SM,
    )

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument(
        "-o",
        "--output",
        help="Output directory relative to each sample directory. Default: mip",
        default="mip",
        action=SM,
    )
    opts.add_argument(
        "-c",
        "--channel",
        help="Channel number for .czi and .zarr inputs. Default: 0",
        default=0,
        type=int,
        action=SM,
    )
    opts.add_argument(
        "-ow",
        "--overwrite",
        help="Overwrite existing MIP files. Default: False",
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


def resolve_img_path(sample_path, path_or_pattern):
    """Resolve an input path or return the first glob match within a sample."""
    path_or_pattern = Path(path_or_pattern)

    if path_or_pattern.is_absolute():
        return path_or_pattern if path_or_pattern.exists() else None

    return next(sample_path.glob(str(path_or_pattern)), None)


@print_func_name_args_times()
def max_intensity_projections(img):
    """Create x-, y-, and z-axis MIPs from an ``xyz``-ordered 3D ndarray.

    The returned arrays use standard image row/column layout:
    ``mip_x`` is ``zy``, ``mip_y`` is ``zx``, and ``mip_z`` is ``yx``.

    Parameters
    ----------
    img : np.ndarray
        Three-dimensional image with axes ordered as ``xyz``.

    Returns
    -------
    dict[str, np.ndarray]
        Mapping of the collapsed axis (``x``, ``y``, or ``z``) to its 2D MIP.
    """
    if not isinstance(img, np.ndarray):
        raise TypeError("Input image must be a numpy ndarray.")
    if img.ndim != 3:
        raise ValueError(f"Input image must be 3D; received shape {img.shape}.")

    return {
        "x": np.max(img, axis=0).T,  # yz -> rows z, columns y
        "y": np.max(img, axis=1).T,  # xz -> rows z, columns x
        "z": np.max(img, axis=2).T,  # xy -> rows y, columns x
    }


@print_func_name_args_times()
def save_mips(mips, output_dir, overwrite=False):
    """Save axis-keyed MIPs as ``mip_x.tif``, ``mip_y.tif``, and ``mip_z.tif``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for axis in ("x", "y", "z"):
        output_path = output_dir / f"mip_{axis}.tif"

        if output_path.exists() and not overwrite:
            print(f"\n    {output_path} already exists. Skipping.")
            continue

        tifffile.imwrite(output_path, mips[axis])
        saved_paths.append(output_path)

        if Configuration.verbose:
            print(f"\n    Output: [default bold]{output_path}")

    return saved_paths


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    progress, task_id = initialize_progress_bar(
        len(sample_paths),
        "[red]Creating maximum intensity projections...",
    )
    with Live(progress):
        for sample_path in sample_paths:
            sample_path = Path(sample_path)
            output_dir = sample_path / args.output
            output_paths = [output_dir / f"mip_{axis}.tif" for axis in "xyz"]

            if all(path.exists() for path in output_paths) and not args.overwrite:
                print(f"\n    MIPs already exist in {output_dir}. Skipping.")
                progress.update(task_id, advance=1)
                continue

            img_path = resolve_img_path(sample_path, args.input)
            if img_path is None:
                print(
                    f"\n    [red1]No files match the path or pattern "
                    f"{args.input} in {sample_path}\n"
                )
                progress.update(task_id, advance=1)
                continue

            img = load_3D_img(
                img_path,
                channel=args.channel,
                desired_axis_order="xyz",
                verbose=args.verbose,
            )
            mips = max_intensity_projections(img)
            save_mips(mips, output_dir, overwrite=args.overwrite)
            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == "__main__":
    main()
