#!/usr/bin/env python3

"""
Use ``coords_resample_points`` (``resample_points``) from UNRAVEL to resample a set of points (coordinates) and optionally convert them to an image, accounting for the number of detections at each voxel.

Input image types:
    .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

Outputs:
    - Output image types: .nii.gz, .tif series, .h5, .zarr
    - A CSV file where each row represents a resampled point corresponding to a detection in the 3D image.
    - A 3D image where each voxel contains the number of detections at that location.

Usage: 
------
    coords_resample_points -i path/points.csv -ri path/ref_image.nii.gz -cr 3.52 3.52 6 -tr 50 [-co path/resampled_points.csv] [-io path/resampled_image.nii.gz] [-thr 20000 or -uthr 20000] [-v]
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install


from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.coordinates.points_to_img import points_to_img, threshold_points_by_region_id


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='CSV w/ columns: x, y, z, Region_ID (e.g., from ``rstats``)', required=True, action=SM)
    reqs.add_argument('-ri', '--ref_img', help='Path to a reference image .nii.gz for setting the output image resolution and shape [and saving if .nii.gz output].', required=True, action=SM)
    reqs.add_argument('-cr', '--current_res', help="Current resolution in micrometers (e.g., 3.52 3.52 6 for anisotropic or 10 for isotropic).", nargs='*', required=True, type=float, action=SM)
    reqs.add_argument('-tr', '--target_res', help="Target resolution in micrometers (e.g., 50 for isotropic).", required=True, type=float, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-co', '--csv_output', help="Optional: Path to save resampled points in a CSV.", action=SM)
    opts.add_argument('-io', '--img_output', help="Optional: Path to save resampled points as an image.", action=SM)
    opts.add_argument('-thr', '--thresh', help='Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data)', type=float, action=SM)
    opts.add_argument('-uthr', '--upper_thr', help='Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data)', type=float, action=SM)

    col_args = parser.add_argument_group("Column arguments")
    col_args.add_argument("-x", "--x_col", help="Column name for x coordinates in the input CSV. Default: x", default="x", action=SM)
    col_args.add_argument("-y", "--y_col", help="Column name for y coordinates in the input CSV. Default: y", default="y", action=SM)
    col_args.add_argument("-z", "--z_col", help="Column name for z coordinates in the input CSV. Default: z", default="z", action=SM)
    col_args.add_argument("-ox", "--out_x_col", help="Column name for resampled x coordinates in the output CSV. Default: x_resampled", default="x_resampled", action=SM)
    col_args.add_argument("-oy", "--out_y_col", help="Column name for resampled y coordinates in the output CSV. Default: y_resampled", default="y_resampled", action=SM)
    col_args.add_argument("-oz", "--out_z_col", help="Column name for resampled z coordinates in the output CSV. Default: z_resampled", default="z_resampled", action=SM)
    col_args.add_argument("-c", "--region-id-col", help="Column name for region IDs used for filtering (default: Region_ID). Set to None to disable filtering.", default="Region_ID", action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def resample_and_convert_points(points_csv_input_path, current_res, target_res, ref_img, thresh=None, upper_thresh=None, region_id_col="Region_ID", x_col="x", y_col="y", z_col="z", out_x_col="x_resampled", out_y_col="y_resampled", out_z_col="z_resampled", verbose=False):
    """Resample a set of points and optionally convert them to an image.

    Parameters:
    -----------
    points_csv_input_path : str
        Path to the CSV file containing the points with columns 'x', 'y', 'z', and <region_id_col>.
    
    current_res : tuple of floats or float
        The current resolution of the points in micrometers, as (x_res, y_res, z_res) or a single float value for isotropic resampling.

    target_res : tuple of floats or float
        The target resolution of the points in micrometers, as (x_res, y_res, z_res) or a single float value for isotropic resampling.

    ref_img : numpy.ndarray
        Reference image for the output image shape and resolution.

    thresh : float, optional
        Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data).

    upper_thresh : float, optional
        Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data).

    region_id_col : str, optional
        The name of the column in the input CSV that contains the region IDs used for filtering. Default is "Region_ID". Set to None to disable filtering.

    x_col, y_col, z_col : str, optional
        Column names for the x, y, z coordinates in the input CSV. Defaults are "x", "y", and "z".

    out_x_col, out_y_col, out_z_col : str, optional
        Column names for the resampled x, y, z coordinates in the output CSV. Defaults are "x_resampled", "y_resampled", and "z_resampled".

    Returns:
    --------
    points_resampled_df : pandas.DataFrame
        The resampled points with columns 'x', 'y', 'z', and <region_id_col> (if present in the input).

    points_resampled_img : numpy.ndarray or None
        The resampled image where each voxel contains the number of detections at that location. 
        Returns `None` if `output_img_path` is not provided.
    """
    # Check if input file exists
    if not Path(points_csv_input_path).exists():
        raise FileNotFoundError(f"\n    [red1]Input file not found: {points_csv_input_path}\n")

    # Handle the case where current_res is passed as a single-element list
    if isinstance(current_res, list) and len(current_res) == 1:
        current_res = current_res[0]
    
    # Ensure that the current_res and target_res are either a single float or a tuple/list of 3 floats
    if isinstance(current_res, (int, float)):
        current_res = (current_res, current_res, current_res)
    elif isinstance(current_res, (list, tuple)) and len(current_res) != 3:
        raise ValueError("\n    [red1]current_res must be a single float or a tuple/list of 3 floats (x_res, y_res, z_res).\n")

    if isinstance(target_res, (int, float)):
        target_res = (target_res, target_res, target_res)
    elif isinstance(target_res, (list, tuple)) and len(target_res) != 3:
        raise ValueError("\n    [red1]target_res must be a single float or a tuple/list of 3 floats (x_res, y_res, z_res).\n")

    # Load and prepare points
    points_df = pd.read_csv(points_csv_input_path)

    if 'count' in points_df.columns:
        print("\n    [red1]The input CSV file contains a 'count' column. Please use `coords_points_compressor` to unpack the points before rerunning this script.\n")
        import sys; sys.exit()

    if region_id_col == "None":
        if verbose:
            print("[yellow]Skipping region-based filtering (--region-id-col None)[/]")

    elif region_id_col not in points_df.columns:
        raise ValueError(
            f"Column '{region_id_col}' not found. "
            "Use --region-id-col None to disable filtering."
        )

    else:
        points_df = threshold_points_by_region_id(
            points_df,
            thresh=thresh,
            upper_thresh=upper_thresh,
            region_id_col=region_id_col,
        )

    # Convert voxel coordinates to physical space
    points_ndarray_physical = points_df[[x_col, y_col, z_col]].values * np.array(current_res)

    # Resample the points to the target resolution
    points_ndarray_resampled = points_ndarray_physical / np.array(target_res)

    # Convert the resampled points to a DataFrame
    points_resampled_df = points_df.copy()
    points_resampled_df[out_x_col] = points_ndarray_resampled[:, 0]
    points_resampled_df[out_y_col] = points_ndarray_resampled[:, 1]
    points_resampled_df[out_z_col] = points_ndarray_resampled[:, 2]

    # Create an image from the points using the reference image
    points_resampled_img = points_to_img(points_ndarray_resampled, ref_img=ref_img)

    return points_resampled_df, points_resampled_img


@log_command
def main():

    install() 
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    ref_img = load_3D_img(args.ref_img, verbose=args.verbose)

    # Resample and convert the points
    points_resampled_df, points_resampled_img = resample_and_convert_points(args.input, args.current_res, args.target_res, ref_img, args.thresh, args.upper_thr, region_id_col=args.region_id_col, verbose=args.verbose)

    # Save the resampled points to a CSV file
    if args.csv_output:
        csv_output_path = Path(args.csv_output)
        csv_output_path.parent.mkdir(exist_ok=True, parents=True)
        points_resampled_df.to_csv(csv_output_path, index=False)
        print(f"\n    Points saved to: {csv_output_path}\n")

    # Save the image
    if args.img_output:
        save_3D_img(points_resampled_img, args.img_output, reference_img=args.ref_img, verbose=args.verbose)

    verbose_end_msg()

if __name__ == "__main__":
    main()
