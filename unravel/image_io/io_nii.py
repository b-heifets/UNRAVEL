#!/usr/bin/env python3

"""
Use ``io_nii`` from UNRAVEL to convert the data type of a .nii.gz image and optionally scale the data.

Usage:
------
    io_nii -i path/img.nii.gz -d float32

Usage for z-score scaling (if 8 bit is needed):
-----------------------------------------------
    io_nii -i path/img.nii.gz -d uint8 -z

Possible numpy data types: 
    - Unsigned Integer: uint8, uint16, uint32, uint64
    - Signed Integer: int8, int16, int32, int64
    - Floating Point: float32, float64

With --scale, the min intensity becomes dtype min and max intensity becomes dtype max. Every other intensity is scaled accordingly.
With --binary, the image is binarized (0 or 1).
With --zscore, the range of z-scored data from -3 to 3 is converted to 0 to 255.
With --fixed_scale, the data is scaled using the provided min and max values.
"""

import argparse
import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Convert the data type of a .nii.gz image', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-d', '--data_type', help='Data type of output. For example: uint16 (numpy conventions)', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/new_img.nii.gz. Default: path/img_dtype.nii.gz', action=SM)
    parser.add_argument('-f', '--fixed_scale', help='Scale data using fixed min and max values. Supply as "min,max"', default=None)
    parser.add_argument('-s', '--scale', help='Scale the data to the range of the new data type', action='store_true', default=False)
    parser.add_argument('-b', '--binary', help='Convert to binary image.', action='store_true', default=False)
    parser.add_argument('-z', '--zscore', help='Convert the range of z-scored data (use uint8 data type).', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def convert_dtype(ndarray, data_type, scale_mode='none', fixed_scale_range=None, zscore_range=(-3, 3), target_range=(0, 255)):
    """
    Convert the data type of an ndarray and optionally scale the data.

    Parameters:
    - ndarray: Input ndarray.
    - data_type: Target data type.
    - scale_mode: 'none', 'standard', or 'zscore'. Determines the scaling approach.
    - fixed_scale_range: Tuple indicating the fixed range for scaling if scale_mode is 'fixed'.
    - zscore_range: Tuple indicating the z-score range for scaling if scale_mode is 'zscore'.
    - target_range: Tuple indicating the target range for the data type conversion.

    Returns:
    - Converted ndarray with the specified data type and scaling.
    """
    if scale_mode != 'none':
        if scale_mode == 'standard':
            print("Applying standard scaling...")
            data_min, data_max = ndarray.min(), ndarray.max()
            ndarray = (ndarray - data_min) / (data_max - data_min) * (target_range[1] - target_range[0]) + target_range[0]
        elif scale_mode == 'fixed' and fixed_scale_range:
            min_val, max_val = fixed_scale_range
            print(f"Applying fixed range scaling from {min_val} to {max_val}...")
            ndarray = (ndarray - min_val) / (max_val - min_val) * (target_range[1] - target_range[0]) + target_range[0]
            ndarray = np.clip(ndarray, target_range[0], target_range[1])
        elif scale_mode == 'zscore':
            print("Applying z-score based scaling (converting range from -3 to 3 to 0 to 255)...")
            scale = (target_range[1] - target_range[0]) / (zscore_range[1] - zscore_range[0])
            offset = target_range[0] - zscore_range[0] * scale
            ndarray = ndarray * scale + offset
            ndarray = np.clip(ndarray, target_range[0], target_range[1])

    # Clip the data to the target range if the data type is integer
    if np.issubdtype(np.dtype(data_type), np.integer):
        dtype_info = np.iinfo(data_type) if np.issubdtype(np.dtype(data_type), np.integer) else np.finfo(data_type)
        ndarray = np.clip(ndarray, dtype_info.min, dtype_info.max)

    return ndarray.astype(np.dtype(data_type))


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the .nii.gz file
    nii_path = args.input if args.input.endswith('.nii.gz') else f'{args.input}.nii.gz'
    nii = nib.load(nii_path)

    # Convert the data to a numpy array
    img = nii.get_fdata(dtype=np.float32)

    # Convert the ndarray to the input data type
    img = img.astype(args.data_type)

    # Optionally binarize the image
    if args.binary:
        img = np.where(img > 0, 1, 0)

    # Determine the scaling mode
    scale_mode = 'standard' if args.scale else 'fixed' if args.fixed_scale else 'zscore' if args.zscore else 'none'

    # Determine target range based on specified data type and scaling mode
    if args.zscore:
        if args.data_type in ['float32', 'float64']:
            # For floating-point types with z-score scaling, use the z-score range itself or a modified version
            target_range = (-3, 3)
        else:
            # For uint8, map z-scores to the full range of the type
            target_range = (0, 255)
    else:
        if np.issubdtype(np.dtype(args.data_type), np.integer):
            dtype_info = np.iinfo(args.data_type)
        else:
            dtype_info = np.finfo(args.data_type)
        target_range = (dtype_info.min, dtype_info.max)

    # Prepare fixed scale range if specified
    fixed_scale_range = None
    if args.fixed_scale:
        fixed_scale_range = tuple(float(x) for x in args.fixed_scale.split(','))

    # Convert the data type and optionally scale the data
    new_img = convert_dtype(img, args.data_type, scale_mode=scale_mode, fixed_scale_range=fixed_scale_range, target_range=target_range)

    # Update the header's datatype
    new_nii = nib.Nifti1Image(new_img, nii.affine, nii.header)
    new_nii.header.set_data_dtype(np.dtype(args.data_type))

    # Save the new .nii.gz file
    if args.binary:
        output_path = args.output if args.output else nii_path.replace('.nii.gz', f'_bin_{args.data_type}.nii.gz')
    elif args.scale:
        output_path = args.output if args.output else nii_path.replace('.nii.gz', f'_std_scaled_{args.data_type}.nii.gz')
    elif scale_mode == 'zscore':
        output_path = args.output if args.output else nii_path.replace('.nii.gz', f'_z_range_scaled_{args.data_type}.nii.gz')
    else:
        output_path = args.output if args.output else nii_path.replace('.nii.gz', f'_{args.data_type}.nii.gz')
    nib.save(new_nii, output_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()