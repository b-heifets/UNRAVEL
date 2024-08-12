#!/usr/bin/env python3

"""
Use `io_points_to_img` from UNRAVEL to convert a set of points (coordinates) to a 3D image, accounting for voxel intensity (e.g., number of detections).

Usage: 
------
    io_points_to_img  -i path/points.csv -o path/image.nii.gz

Input:
    A CSV file where each row represents a point corresponding to a detection in the 3D image. 
    The coordinates (x, y, z) are derived from the voxel locations in the image, with multiple 
    points generated for voxels with intensities greater than 1.

Output image types:
    .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

"""

import argparse
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description="Populate a 3D image with points based on their coordinates, summing the number of points at each voxel.", formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='CSV w/ columns: x, y, z, Region_ID (e.g., from ``rstats``)', required=True, action=SM)
    parser.add_argument('-o', '--output', help="Path to save the output image.", required=True, action=SM)
    parser.add_argument('-r', '--ref_img', help='Path to a reference image for the output shape [and saving if .nii.gz output]. Use -r or -s.', action=SM)
    parser.add_argument('-s', '--img_shape', help='Shape of the output image (e.g., 100, 100, 100 for x, y, z).', nargs=3, type=int, action=SM)
    parser.add_argument('-thr', '--thresh', help='Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data)', type=float, action=SM)
    parser.add_argument('-uthr', '--upper_thresh', help='Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data)', type=float, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

@print_func_name_args_times()
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
        The filtered DataFrame containing the points with columns 'x', 'y', and 'z'.
    """
    # Remove points that are outside the brain (i.e., 'Region_ID' == 0)
    points_df = points_df[points_df['Region_ID'] != 0]

    # Filter points based on thresholding the 'Region_ID' column
    if thresh:
        points_df = points_df[points_df['Region_ID'] >= thresh]
    elif upper_thresh:
        points_df = points_df[points_df['Region_ID'] <= upper_thresh]

    # Drop the 'Region_ID' column
    points_df = points_df.drop(columns=['Region_ID'])

    return points_df

@print_func_name_args_times()
def load_and_prepare_points(input_path, thresh=None, upper_thresh=None):
    """
    Load points from a CSV file and prepare them by filtering based on Region_ID and adjusting coordinates.

    Parameters:
    -----------
    input_path : str or Path
        Path to the input CSV file containing the points.

    thresh : float, optional
        Threshold to exclude points with Region_ID below this value.

    upper_thresh : float, optional
        Threshold to exclude points with Region_ID above this value.

    Returns:
    --------
    points_ndarray : numpy.ndarray
        A 2D array of shape (n, 3) containing the prepared points.
    """
    points_df = pd.read_csv(input_path)
    points_df = threshold_points_by_region_id(points_df, thresh=thresh, upper_thresh=upper_thresh)
    points_ndarray = points_df.to_numpy()

    # Add a 1 voxel offset since the coordinates are 0-based
    points_ndarray += 1
    return points_ndarray

@print_func_name_args_times()
def create_image_from_points(points_ndarray, ref_img_path=None, img_shape=None):
    """
    Create a 3D image from a set of point coordinates, using a reference image for shape if provided.
    If multiple points fall within the same voxel, the voxel's value is incremented accordingly.

    Parameters:
    -----------
    points_ndarray : numpy.ndarray
        A 2D array of shape (n, 3) where each row represents the (x, y, z) coordinates of a point.

    ref_img : nib.Nifti1Image, optional
        A reference image from which to derive the output shape.

    img_shape : tuple of int, optional
        Shape of the output image if no reference image is provided. The order is (x, y, z).

    Returns:
    --------
    img : numpy.ndarray
        A 3D image created from the input points. Each voxel's value represents the number of points that fall within that voxel.

    Notes:
    ------
    - If the point coordinates are in physical or resampled space, ensure that they are appropriately 
      scaled and aligned with the desired image grid before calling this function.
    - If the count in a voxel exceeds the maximum value for `uint8` (255), the image's data type is 
      automatically promoted to `uint16` to accommodate higher counts.

    Example:
    --------
    >>> points = np.array([[10, 20, 30], [10, 20, 30], [15, 25, 35]])
    >>> img_shape = (50, 50, 50)
    >>> img = create_image_from_points(points, img_shape=img_shape)
    >>> print(img[10, 20, 30])  # Output will be 2, since two points are at this coordinate.
    >>> print(img[15, 25, 35])  # Output will be 1, since one point is at this coordinate.
    """
    if ref_img_path:
        ref_img = load_3D_img(ref_img_path)
        img_shape = ref_img.shape
    elif img_shape is None:
        raise ValueError("Either ref_img or img_shape must be provided.")

    # Create an empty image
    img = np.zeros(img_shape, dtype='uint8')

    # Increment the voxel value for each point's coordinates
    for x, y, z in points_ndarray.astype(int):
        if 0 <= x < img_shape[0] and 0 <= y < img_shape[1] and 0 <= z < img_shape[2]:
            img[x, y, z] += 1
            
            # Promote to uint16 if a voxel's count exceeds 255
            if img[x, y, z] == 255 and img.dtype == 'uint8':
                img = img.astype('uint16')

    return img

@print_func_name_args_times()
def points_to_img(points_csv_path, output_img_path, ref_img_path=None, img_shape=None, thresh=None, upper_thresh=None):
    """
    Convert a set of points to a 3D image, accounting for voxel intensity.

    Parameters:
    -----------
    points_csv_path : str or Path
        Path to the CSV file containing the points.

    output_img_path : str or Path
        Path to save the output image.

    ref_img_path : str or Path, optional
        Path to a reference image for the output shape.

    img_shape : tuple of int, optional
        Shape of the output image if no reference image is provided. The order is (x, y, z).

    thresh : float, optional
        Exclude region IDs below this threshold.

    upper_thresh : float, optional
        Exclude region IDs above this threshold.
    """
    # Load and prepare points
    points_ndarray = load_and_prepare_points(points_csv_path, thresh=thresh, upper_thresh=upper_thresh)

    # Create an image from the points using the specified shape or reference image
    img = create_image_from_points(points_ndarray, ref_img_path=ref_img_path, img_shape=tuple(img_shape) if img_shape else None)

    # Save the image
    save_3D_img(img, output_img_path, reference_img=ref_img_path)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    points_to_img(args.input, args.output, args.ref_img, args.img_shape, args.thresh, args.upper_thresh)

    verbose_end_msg()


if __name__ == '__main__':
    main()
