#!/usr/bin/env python3

"""
Use `img_resample_points` from UNRAVEL to resample a set of points (coordinates) and optionally convert them to an image, accounting for the number of detections at each voxel.

Usage: 
------
    img_resample_points -i path/points.csv -ri path/ref_image.nii.gz -cr 3.52 3.52 6 -tr 50 [-co path/resampled_points.csv] [-io path/resampled_image.nii.gz] [-thr 20000 or -uthr 20000] [-v]

Input image types:
    .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

Output image types:
    .nii.gz, .tif series, .h5, .zarr

Outputs:
    - A CSV file where each row represents a resampled point corresponding to a detection in the 3D image.
    - A 3D image where each voxel contains the number of detections at that location. 
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install


from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.image_io.points_to_img import points_to_img, load_and_prepare_points


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='CSV w/ columns: x, y, z, Region_ID (e.g., from ``rstats``)', required=True, action=SM)
    parser.add_argument('-ri', '--ref_img', help='Path to a reference image .nii.gz for setting the output image resolution and shape [and saving if .nii.gz output].', required=True, action=SM)
    parser.add_argument('-cr', '--current_res', help="Current resolution in micrometers (e.g., 3.52 3.52 6 for anisotropic or 10 for isotropic).", nargs='*', required=True, type=float, action=SM)
    parser.add_argument('-tr', '--target_res', help="Target resolution in micrometers (e.g., 50 for isotropic).", required=True, type=float, action=SM)
    parser.add_argument('-co', '--csv_output', help="Optional: Path to save resampled points in a CSV.", action=SM)
    parser.add_argument('-io', '--img_output', help="Optional: Path to save resampled points as an image.", action=SM)
    parser.add_argument('-thr', '--thresh', help='Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data)', type=float, action=SM)
    parser.add_argument('-uthr', '--upper_thr', help='Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data)', type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def resample_and_convert_points(points_csv_input_path, current_res, target_res, ref_img, thresh=None, upper_thresh=None):
    """Resample a set of points and optionally convert them to an image. 

    Parameters:
    -----------
    points_csv_input_path : str
        Path to the CSV file containing the points with columns 'x', 'y', 'z', and 'Region_ID'.
    
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

    points_csv_output_path : str, optional
        Path to save the resampled points in a CSV file.

    output_img_path : str, optional
        Path to save the resampled points as an image.

    Returns:
    --------
    points_resampled_df : pandas.DataFrame
        The resampled points with columns 'x', 'y', and 'z'.

    points_resampled_img : numpy.ndarray or None
        The resampled image where each voxel contains the number of detections at that location. 
        Returns `None` if `output_img_path` is not provided.
    """
    # Check if input file exists
    if not Path(points_csv_input_path).exists():
        raise FileNotFoundError(f"\n    [red1]Input file not found: {points_csv_input_path}\n")
    
    # Ensure that the current_res and targe_res are either a single float or a tuple/list of 3 floats
    if not isinstance(current_res, (float, list, tuple)) or (isinstance(current_res, (list, tuple)) and len(current_res) != 3):
        raise ValueError("\n    [red1]current_res must be a single float or a tuple/list of 3 floats (x_res, y_res, z_res).\n")
    if not isinstance(target_res, (float, list, tuple)) or (isinstance(target_res, (list, tuple)) and len(target_res) != 3):
        raise ValueError("\n    [red1]target_res must be a single float or a tuple/list of 3 floats (x_res, y_res, z_res).\n")

    # Convert a single float to a tuple
    if isinstance(current_res, (float, int)):
        current_res = (current_res, current_res, current_res)
    if isinstance(target_res, (float, int)):
        target_res = (target_res, target_res, target_res)
    
    # Load and prepare points
    points_ndarray = load_and_prepare_points(points_csv_input_path, thresh=thresh, upper_thresh=upper_thresh)

    # Convert voxel coordinates to physical space
    points_ndarray_physical = points_ndarray * np.array(current_res)

    # Resample the points to the target resolution
    points_ndarray_resampled = points_ndarray_physical / np.array(target_res)

    # Convert the resampled points to a DataFrame
    points_resampled_df = pd.DataFrame(points_ndarray_resampled, columns=['x', 'y', 'z'])

    # Create an image from the points using the reference image
    points_resampled_img = points_to_img(points_ndarray_resampled, ref_img=ref_img)

    return points_resampled_df, points_resampled_img


@log_command
def main():

    install() 
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    ref_img = load_3D_img(args.ref_img)

    # Resample and convert the points
    points_resampled_df, points_resampled_img = resample_and_convert_points(args.input, args.current_res, args.target_res, ref_img, args.thresh, args.upper_thr)

    # Save the resampled points to a CSV file
    if args.csv_output:
        csv_output_path = Path(args.csv_output)
        csv_output_path.parent.mkdir(exist_ok=True, parents=True)
        points_resampled_df.to_csv(csv_output_path, index=False)
        print(f"\n    Points saved to: {csv_output_path}\n")

    # Save the image
    if args.img_output:
        save_3D_img(points_resampled_img, args.img_output, reference_img=args.ref_img)

    verbose_end_msg()

if __name__ == "__main__":
    main()
