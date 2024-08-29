#!/usr/bin/env python3

"""
Use `io_points_to_img` from UNRAVEL to convert a set of points (coordinates) to a 3D image, accounting for the number of detections at each voxel.

Input:
    - A CSV file where each row represents a point corresponding to a detection in the 3D image. 
    - The columns should include 'x', 'y', 'z', and 'Region_ID' (e.g., from ``rstats`` or ``io_img_to_points``).

Output image types:
    .nii.gz, .tif series, .h5, .zarr

Note:
    - Points outside the brain (i.e., 'Region_ID' == 0) are excluded.
    - If the input CSV has a 'count' column, use ``utils_points_compressor`` to unpack the points before running this script.

Usage: 
------
    io_points_to_img  -i path/points.csv -ri path/ref_image [-o path/image] [-thr 20000 or -uthr 20000] [-v]
"""

from pathlib import Path
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/input.csv w/ columns: x, y, z, Region_ID', required=True, action=SM)
    reqs.add_argument('-ri', '--ref_img', help='Path to a reference image for output image shape and saving.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path to save the output image. Default: path/input.nii.gz', default=None, action=SM)
    opts.add_argument('-thr', '--thresh', help='Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data)', type=float, action=SM)
    opts.add_argument('-uthr', '--upper_thr', help='Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data)', type=float, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def threshold_points_by_region_id(points_df, thresh=None, upper_thresh=None):
    """
    Filter the points (i.e., coordinates) based on the 'Region_ID' column. This function removes points that are outside the brain (i.e., 'Region_ID' == 0) and optionally filters points based on a threshold or upper threshold.
    
    Parameters:
    -----------
    points_df : pandas.DataFrame
        A DataFrame containing the points with columns 'x', 'y', 'z', and 'Region_ID'.

    thresh : float, optional
        Exclude region IDs below this threshold.

    upper_thresh : float, optional
        Exclude region IDs above this threshold.

    Returns:
    --------
    points_df : pandas.DataFrame
        The filtered DataFrame containing the points with columns 'x', 'y', 'z', and 'Region_ID'.
    """
    # Remove points that are outside the brain (i.e., 'Region_ID' == 0)
    points_df = points_df[points_df['Region_ID'] != 0]

    # Filter points based on thresholding the 'Region_ID' column
    if thresh:
        points_df = points_df[points_df['Region_ID'] >= thresh]
    if upper_thresh:
        points_df = points_df[points_df['Region_ID'] <= upper_thresh]

    return points_df

@print_func_name_args_times()
def load_and_prepare_points(points_csv_path, thresh=None, upper_thresh=None):
    """
    Load points from a CSV file and prepare them by filtering based on Region_ID and adjusting coordinates.

    Parameters:
    -----------
    points_csv_path : str or Path
        Path to the input CSV file containing the points.

    thresh : float, optional
        Threshold to exclude points with Region_ID below this value.

    upper_thresh : float, optional
        Threshold to exclude points with Region_ID above this value.

    Returns:
    --------
    points_df : pandas.DataFrame
        A DataFrame containing the prepared points with columns 'x', 'y', 'z', and 'Region_ID'.
    """
    points_df = pd.read_csv(points_csv_path)

    # Check if the DataFrame has a count column
    if 'count' in points_df.columns:
        print("\n    [red1]The input CSV file contains a 'count' column. Please use `utils_points_compressor` to unpack the points before rerunning this script.\n")
        import sys ; sys.exit()

    points_df = threshold_points_by_region_id(points_df, thresh=thresh, upper_thresh=upper_thresh)
    return points_df

@print_func_name_args_times()
def points_to_img(points_ndarray, ref_img=None):
    """
    Create a 3D image from a set of point coordinates, using a reference image for shape if provided.
    If multiple points fall within the same voxel, the voxel's value is incremented accordingly.

    Parameters:
    -----------
    points_ndarray : numpy.ndarray
        A 2D array of shape (n, 3) where each row represents the (x, y, z) coordinates of a point.

    ref_img : numpy.ndarray
        A reference image from which to derive the output shape.

    Returns:
    --------
    img : numpy.ndarray
        A 3D image created from the input points. Each voxel's value represents the number of points that fall within that voxel.

    Note:
    -----
    - If the point coordinates are in physical or resampled space, ensure that they are appropriately 
      scaled and aligned with the desired image grid before calling this function.
    - If the count in a voxel exceeds the maximum value for `uint8` (255), the image's data type is 
      automatically promoted to `uint16` to accommodate higher counts.

    Example:
    --------
    >>> points_ndarray = np.array([[10, 20, 30], [10, 20, 30], [15, 25, 35]])
    >>> ref_img = np.zeros((50, 50, 50), dtype='uint8')
    >>> img = points_to_img(points_ndarray, ref_img)
    >>> print(img[10, 20, 30])  # Output will be 2, since two points are at this coordinate.
    >>> print(img[15, 25, 35])  # Output will be 1, since one point is at this coordinate.
    """

    # Create an empty image
    img_shape = ref_img.shape
    img = np.zeros(img_shape, dtype='uint8')

    # Increment the voxel value for each point's coordinates
    for x, y, z in points_ndarray.astype(int):
        if 0 <= x < img_shape[0] and 0 <= y < img_shape[1] and 0 <= z < img_shape[2]:
            img[x, y, z] += 1
            
            # Promote to uint16 if a voxel's count exceeds 255
            if img[x, y, z] == 255 and img.dtype == 'uint8':
                img = img.astype('uint16')

    return img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load and prepare points
    points_df = load_and_prepare_points(points_csv_path=args.input, thresh=args.thresh, upper_thresh=args.upper_thr)

    # Extract the ndarray of coordinates from the DataFrame
    points_ndarray = points_df[['x', 'y', 'z']].values

    # Create an image from the points using a reference image to determine the shape
    ref_img = load_3D_img(args.ref_img)
    img = points_to_img(points_ndarray, ref_img)

    # Save the image
    if args.output:
        output_img_path = Path(args.output)
        output_img_path.parent.mkdir(exist_ok=True, parents=True)
    else:
        output_img_path = args.input.replace('.csv', '.nii.gz')
    save_3D_img(img, output_img_path, reference_img=args.ref_img)

    verbose_end_msg()


if __name__ == '__main__':
    main()
