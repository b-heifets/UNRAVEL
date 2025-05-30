#!/usr/bin/env python3

"""
Use ``img_math`` (``math``) from UNRAVEL to perform mathematical operations on 3D images.

Inputs: 
    - Any of the following formats: .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr
    
Outputs:
    - .nii.gz, .tif series, or .zarr depending on the output path extension

Supported Operations:
    - Use with the ``-n`` or ``--operation`` flag:
    - Arithmetic: ``+``, ``-``, ``<asterisk>``, ``/``, ``//``, ``%``, ``<asterisk><asterisk>``  
    - Comparison: ``==``, ``!=``, ``>``, ``>=``, ``<``, ``<=``  
    - Logical: ``and``, ``or``, ``xor``, ``not``  
    - Other: ``abs_diff`` (absolute difference)

Thresholding:
    Optionally apply a threshold (lower and/or upper) to the result using:
    - --threshold      : Lower threshold
    - --upper_thres    : Upper threshold
    - --True_val       : Value to assign if the condition is met (default: 1)
    - --False_val      : Value to assign if the condition is not met (default: 0)

Usage to add two images and binarize the result:
------------------------------------------------
    img_math -i A.nii.gz B.nii.gz -n + -t 0.5 -o result.nii.gz -r A.nii.gz -d uint8

Usage multiply three images and save as Zarr:
---------------------------------------------
    img_math -i A.nii.gz B.nii.gz C.nii.gz -n <asterisk> -o result.zarr

Usage to binarize a single image and set to 8 bit:
--------------------------------------------------
    img_math -i A.nii.gz -t 0.5 -o binarized.nii.gz -r A.nii.gz -d uint8
"""


import numpy as np
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_nii, save_as_tifs, save_as_zarr
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--images', help="Paths to the input images. (path/image1 path/image2 ...)", nargs='*', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='Path to the output image', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-n', '--operation', help="Numpy operation to perform (+, -, *, /, etc.).", default=None, action=SM)
    opts.add_argument('-t', '--threshold', help='Apply a lower threshold.', default=None, type=float, action=SM)
    opts.add_argument('-ut', '--upper_thres', help='Upper threshold for thresholding.', default=None, type=float, action=SM)
    opts.add_argument('-T', '--True_val', help='Value to assign when threshold condition is true. Default: 1', default=1, type=float, action=SM)
    opts.add_argument('-F', '--False_val', help='Value to assign when threshold condition is false. Default: 0', default=0, type=float, action=SM)
    opts.add_argument('-d', '--dtype', help='Numpy array data type', default=None, action=SM)
    opts.add_argument('-r', '--reference', help='Reference image for .nii.gz metadata.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args() 

# TODO: Add support for chaining operations (e.g., img1 + img2 - img3 * img4)
# TODO: Add the ability to apply operations to a single image (e.g., img1 * 2)

@print_func_name_args_times()
def apply_operation(image1, image2, operation):
    """
    Apply a mathematical operation to two ndarrays (images).

    Supported operations include addition, subtraction, multiplication, division, and more.

    Parameters
    ----------
    image1 : np.ndarray
        First image.
    image2 : np.ndarray
        Second image.
    operation : str
        The operation to perform. Supported operations are:
        ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``, ``==``, ``!=``, ``>``, ``>=``, ``<``, ``<=``,
        ``and``, ``or``, ``xor``, ``not``, ``abs_diff``.

    Notes
    -----
    - Element-wise comparison operations (``==``, ``!=``, ``>``, ``>=``, ``<``, ``<=``) return a boolean array.
    - Logical operations (``and``, ``or``, ``xor``, ``not``) also return a boolean array.
    - The ``abs_diff`` operation computes the absolute difference between the two images.

    Returns
    -------
    np.ndarray
        Resulting image after applying the operation.
    """
        
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
        'not': np.logical_not, # Inverts boolean values of a single image (image1)
        'abs_diff': lambda x, y: np.abs(x - y), # Absolute difference
    }
    
    if operation == 'not':
        return operations['not'](image1)

    if operation in operations:
        return operations[operation](image1, image2)
    else:
        raise ValueError("Unsupported operation.")

@print_func_name_args_times()
def threshold_image(image, lower_thr=None, upper_thr=None, true_val=1, false_val=0):
    """Apply lower and/or upper thresholding to an image."""
    mask = np.ones_like(image, dtype=bool)
    if lower_thr is not None:
        mask &= image >= lower_thr
    if upper_thr is not None:
        mask &= image <= upper_thr
    return np.where(mask, true_val, false_val)

@log_command
def main():    
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if not args.images:
        raise ValueError("At least one image must be specified with --images.")

    images = [load_3D_img(img_path, verbose=args.verbose) for img_path in args.images]

    # Ensure all images are the same shape
    shape0 = images[0].shape
    if not all(img.shape == shape0 for img in images):
        raise ValueError("All input images must have the same shape.")

    # If an operation is specified and there is more than one image, reduce using the operation
    if args.operation:
        if len(images) == 1:
            raise ValueError("At least two images are required for operation: {}".format(args.operation))
        result = images[0]
        for img in images[1:]:
            result = apply_operation(result, img, args.operation)
    else:
        if len(images) > 1:
            raise ValueError("Multiple images provided, but no operation specified.")
        result = images[0]

    # Apply thresholding
    if args.threshold is not None or args.upper_thres is not None:
        result = threshold_image(
            result,
            lower_thr=args.threshold,
            upper_thr=args.upper_thres,
            true_val=args.True_val,
            false_val=args.False_val
        )

    # Set data type
    if args.dtype: 
        result = result.astype(args.dtype)

    # Save image    
    if args.output.endswith('.nii.gz'):
        save_as_nii(result, args.output, reference=args.reference, data_type=args.dtype)
    elif args.output.endswith('.tif'):
        save_as_tifs(result, args.output)
    elif args.output.endswith('.zarr'):
        save_as_zarr(result, args.output)

    verbose_end_msg()
    
if __name__ == '__main__':
    main()
