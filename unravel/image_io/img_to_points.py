#!/usr/bin/env python3

"""
Use `io_img_to_points` from UNRAVEL to convert non-zero voxels in a 3D image to a set of points, accounting for voxel intensity (e.g., number of detections).

Input image types:
    - .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

Output:
    - A CSV file where each row represents a point corresponding to a detection in the 3D image. 
    - The coordinates (x, y, z) are derived from the voxel locations in the image, with multiple points generated for voxels with intensities greater than 1.
    - An optional 'Region_ID' column is added based on the corresponding atlas image.

Usage: 
------
    io_img_to_points -i path/image [-a path/atlas_image.nii.gz] [-o path/points.csv] [-v]
"""

from pathlib import Path
import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input 3D image.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-a', '--atlas_img', help="Path to the atlas image matching -i for adding a 'Region_ID' column to the CSV.", action=SM)
    opts.add_argument('-o', '--output', help='Path to save the output points (CSV format). Default: path/input_points.csv', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def img_to_points(img, atlas_img=None):
    """
    Converts non-zero voxel coordinates in a 3D ndarray to a list of points, accounting for voxel intensity.
    Optionally adds a 'Region_ID' based on the corresponding atlas image.

    Parameters:
    -----------
    img : numpy.ndarray
        The 3D array representing the image data, where voxel intensities > 0 indicate the number of detections.
    
    atlas_img : numpy.ndarray, optional
        The 3D array representing the atlas image data. If provided, a 'Region_ID' column will be added to the output points.

    Returns:
    --------
    points : numpy.ndarray
        An array of points where each row corresponds to the (x, y, z) coordinates of a detection.
        If atlas_img is provided, each point will have an additional 'Region_ID' column.

    Note:
    -----
    Convert the points to a DataFrame using:
    >>> points_df = pd.DataFrame(points_ndarray, columns=['x', 'y', 'z'])
    or
    >>> points_df = pd.DataFrame(points_ndarray, columns=['x', 'y', 'z', 'Region_ID'])  # With atlas_img
    """
    points = []
    # Find the coordinates of non-zero voxels
    coords = np.argwhere(img > 0)
    
    for coord in coords:
        point_intensity = int(img[tuple(coord)])

        # Create multiple points for the same coordinate based on intensity
        for _ in range(point_intensity):
            if atlas_img is not None:
                region_id = int(atlas_img[tuple(coord)])  # Look up Region_ID in the atlas image
                points.append(np.append(coord, region_id))  # Append coordinate and Region_ID
            else:
                points.append(coord)
    
    return np.array(points)


@log_command
def main():

    install() 
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img = load_3D_img(args.input)
    atlas_img = load_3D_img(args.atlas_img) if args.atlas_img else None

    # Convert the image to points
    points_ndarray = img_to_points(img, atlas_img=atlas_img)

    if int(points_ndarray.shape[1]) == 3:
        points_df = pd.DataFrame(points_ndarray, columns=['x', 'y', 'z'])
    elif int(points_ndarray.shape[1]) == 4:
        points_df = pd.DataFrame(points_ndarray, columns=['x', 'y', 'z', 'Region_ID'])

    # Save the points to a CSV file
    if args.output:
        csv_output_path = Path(args.output)
        csv_output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        csv_output_path = args.input.replace('.nii.gz', '_points.csv')
    points_df.to_csv(csv_output_path, index=False)
    print(f"\n    Points saved to {csv_output_path}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()
