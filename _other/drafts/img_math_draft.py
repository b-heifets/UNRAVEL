#!/usr/bin/env python3

import argparse
import numpy as np
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii, save_as_tifs, save_as_zarr
from unravel.core.utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description='This script performs element-wise mathematical operations on two images and saves the result.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--images', help="Paths to the input images. (path/image1 path/image2)", nargs=2, required=True, action=SM)
    parser.add_argument('-n', '--operation', help="Numpy operation to perform (+, -, *, /, etc.).", required=True, action=SM)
    parser.add_argument('-o', '--output', help='Path to the output image', required=True, action=SM)
    parser.add_argument('-t', '--threshold', help='Threshold the output image.', default=None, type=float, action=SM)
    parser.add_argument('-ut', '--upper_thres', help='Upper threshold for thresholding.', default=None, type=float, action=SM)
    parser.add_argument('-T', '--True_val', help='Value to assign when threshold condition is true.', default=1, type=float, action=SM)
    parser.add_argument('-F', '--False_val', help='Value to assign when threshold condition is false.', default=0, type=float, action=SM)
    parser.add_argument('-d', '--dtype', help='Numpy array data type', default=None, action=SM)
    parser.add_argument('-r', '--reference', help='Reference image for .nii.gz metadata.', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Input image types: .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr
Output image types: .nii.gz, .tif series, .zarr

Example usage: img_math.py -i image1.nii.gz image2.nii.gz -n + -o result.nii.gz -b 0.5 -d float32

Operations:
    +: Add
    -: Subtract
    *: Multiply
    /: Divide
    //: Floor divide
    %: Modulo
    **: Power
    ==: Equal (element-wise comparison)
    !=: Not equal
    >: Greater
    >=: Greater or equal
    <: Less
    <=: Less or equal
    and: Logical AND
    or: Logical OR
    xor: Logical XOR
    not: Logical NOT
    abs_diff: Absolute difference


"""
    return parser.parse_args() 



def apply_operation(image1, image2, operation):
    """Apply the specified operation on two images."""
    operations = {
        '+': np.add,
        '-': np.subtract,
        '*': np.multiply,
        '/': np.divide, 
        '//': np.floor_divide,
        '%': np.mod,
        '**': np.power,
        '==': np.equal, # Element-wise comparison (e.g., for thresholding)
        '!=': np.not_equal, # Element-wise comparison
        '>': np.greater, # Element-wise comparison
        '>=': np.greater_equal, # Element-wise comparison
        '<': np.less, # Element-wise comparison
        '<=': np.less_equal, # Element-wise comparison
        'and': np.logical_and, # Element-wise comparison
        'or': np.logical_or, # Element-wise comparison
        'xor': np.logical_xor, # Element-wise comparison
        'not': np.logical_not, # Element-wise comparison
        'abs_diff': lambda x, y: np.abs(x - y), # Absolute difference
    }
    
    if operation in operations:
        return operations[operation](image1, image2)
    else:
        raise ValueError("Unsupported operation.")
    
def threshold_image(image, lower_thr=None, upper_thr=None, true_val=1, false_val=0):
    """Apply lower and upper thresholding to an image with specified values for true and false conditions."""
    if lower_thr is not None:
        image = np.where(image >= lower_thr, image, false_val)
    if upper_thr is not None:
        image = np.where(image <= upper_thr, image, false_val)
    # This assumes you want to keep the original value when the condition is true, 
    # and set to `false_val` otherwise. Adjust as needed.
    return image

def binarize_image(image, threshold, true_val=1, false_val=0):
    """Binarize an image based on a threshold with specified values for true and false conditions."""
    return np.where(image > threshold, true_val, false_val)

def main():    
    args = parse_args()

    image1 = load_3D_img(args.image1)
    image2 = load_3D_img(args.image2)

    # Ensure image dimensions match
    if image1.shape != image2.shape:
        raise ValueError("Image dimensions do not match.")

    # Apply operation
    result = apply_operation(image1, image2, args.operation)

    # TODO: Add in args.True_val and args.False_val to threshold_image and binarize_image
    # Threshold image 
    if args.threshold is not None:
        result = threshold_image(result, args.threshold, true_val=1, false_val=0)
    if args.upper_thres is not None:
        result = threshold_image(result, upper_thr=args.upper_thres, true_val=1, false_val=0)

    # Binarize image
    if args.binarize is not None:
        result = binarize_image(result, args.binarize)

    # Set data type
    if args.dtype: 
        result = result.astype(args.dtype)

    # Save image    
    if args.output.endswith('.nii.gz'):
        save_as_nii(result, args.output, reference=args.reference)
    elif args.output.endswith('.tif'):
        save_as_tifs(result, args.output)
    elif args.output.endswith('.zarr'):
        save_as_zarr(result, args.output)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
