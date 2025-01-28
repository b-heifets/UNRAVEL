#!/usr/bin/env python3

"""
Use /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_resample_w_summing.py from UNRAVEL to resample a 3D MERFISH-CCF image (10x10x200) to 30x30x200 µm resolution.

Usage:
------
    /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/_other/drafts/merfish_resample_w_summing.py -i image.nii.gz [-o image_resampled.nii.gz] [-v] [--method sum|average|nn]
"""

import nibabel as nib
import numpy as np
from rich.traceback import install
import scipy.ndimage as ndimage  # For nearest-neighbor interpolation

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/input_image.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='path/output_image.nii.gz. Default: None (saves as path/input_image_resampled.nii.gz)', default=None, action=SM)
    opts.add_argument('--method', choices=['sum', 'average', 'nn'], default='sum', help="Resampling method: 'sum', 'average', or 'nn' for nearest neighbor.")

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def resample_with_summing(arr, voxel_size=(10, 10, 200), new_voxel_size=(30, 30, 200), method="sum"):
    """
    Resample a 3D array by summing or averaging values in blocks, or using nearest-neighbor interpolation.

    Parameters:
    -----------
    arr : np.ndarray
        The input 3D array with shape (x, y, z).
    voxel_size : tuple
        The original voxel size in microns (x_size, y_size, z_size).
    new_voxel_size : tuple
        The target voxel size in microns (x_size, y_size, z_size).
    method : str
        The resampling method, either "sum", "average", or "nn" (nearest neighbor interpolation).

    Returns:
    --------
    np.ndarray
        The resampled 3D array with the new resolution.
    """
    if method == 'nn':  # Nearest-neighbor interpolation
        zoom_factors = np.array(voxel_size) / np.array(new_voxel_size)
        resampled_arr = ndimage.zoom(arr, zoom=zoom_factors, order=0)  # NN interpolation
        return resampled_arr

    # Calculate the downsampling factor in the x and y dimensions
    factor_xy = new_voxel_size[0] // voxel_size[0]  # 30 // 10 = 3

    # Determine new sizes to make the array divisible by the downsampling factors
    new_xy_size = (1100 // 3) * 3  # 1100 // 3 = 366, 366 * 3 = 1098

    # Crop the array to make it divisible by 3 in the x and y dimensions
    cropped_arr = arr[:new_xy_size, :new_xy_size, :]

    # Reshape the array into blocks of size (factor_x, factor_y) in the x and y dimensions
    reshaped_arr = cropped_arr.reshape(new_xy_size // factor_xy, factor_xy, new_xy_size // factor_xy, factor_xy, 76)  # (366, 3, 366, 3, 76)

    if method == 'sum':
        # Sum over the blocks in x and y dimensions (sum over axis 1 and 3)
        downsampled_arr = reshaped_arr.sum(axis=(1, 3))
    elif method == 'average':
        # Average over the blocks in x and y dimensions (sum over axis 1 and 3, then divide)
        downsampled_arr = reshaped_arr.mean(axis=(1, 3))

    return downsampled_arr


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    nii = nib.load(args.input)
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

    img_resampled = resample_with_summing(img, voxel_size=(10, 10, 200), new_voxel_size=(30, 30, 200), method=args.method)

    if args.output is None:
        img_resampled_path = args.input.replace('.nii.gz', '_resampled.nii.gz')
    else:
        img_resampled_path = args.output

    # Update the affine matrix
    affine_ndarray = np.array(nii.affine)
    new_affine = affine_ndarray.copy()
    original_res_in_um = np.array([10, 10, 200])
    target_res_in_um = np.array([30, 30, 200])
    scaling_factors = target_res_in_um / original_res_in_um
    new_affine[0:3, 0:3] *= scaling_factors

    # Update the header
    new_header = nii.header.copy()
    new_header.set_zooms((30, 30, 200))

    # Create the resampled NIfTI image
    resampled_nii = nib.Nifti1Image(img_resampled, new_affine, new_header)

    # Save the resampled image
    nib.save(resampled_nii, img_resampled_path)

    print(f"\n    Resampled image saved to {img_resampled_path}")

    verbose_end_msg()


if __name__ == '__main__':
    main()
