#!/usr/bin/env python3

"""
Use ``img_modify_labels`` (``ml``) from UNRAVEL to modify specified label IDs in a NIfTI image.

Usage: 
------
    img_modify_labels -i path/image.nii.gz -ids 1 2 3 -o path/image.nii.gz [-val 0] [--retain_IDs] [--binarize] [-v]
"""

import numpy as np
import nibabel as nib
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, print_func_name_args_times, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image.nii.gz', required=True, action=SM)
    reqs.add_argument('-ids', '--label_IDs', help='Space-separated list of label IDs to modify.', nargs='*', type=int, default=None, required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/image.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-val', '--value', help='Intensity to set for specified labels (default: 0).', type=int, default=0)
    opts.add_argument('-r', '--retain_IDs', help='Retain only specified label IDs, setting others using -val.', action='store_true', default=False)
    opts.add_argument('-b', '--binarize', help='Binarize the output image (set all non-zero values to 1).', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def set_labels(img, label_IDs, value=0):
    """
    Set specified label IDs in the ndarray to a given value.
    
    Parameters
    ----------
    img : ndarray
        The input image as a numpy ndarray.
    label_IDs : list of int
        The label IDs to set to a specific value.
    value : int
        The intensity to set for specified label IDs (default: 0).
    
    Returns
    -------
    ndarray
        The modified image with specified label IDs set to the given value.
    """
    img[np.isin(img, label_IDs)] = value  # Creates a boolean mask of the label IDs and sets them to the specified value
    return img

def retain_labels(img, label_IDs, omit_value=0):
    """
    Retain only specified label IDs in the image, setting others to omit_value.
    
    Parameters
    ----------
    img : ndarray
        The input image as a numpy ndarray.
    label_IDs : list of int
        The label IDs to retain.
    omit_value : int
        The intensity to set for labels not in label_IDs (default: 0).

    Returns
    -------
    ndarray
        The modified image with only the specified label IDs retained.
    """
    img[~np.isin(img, label_IDs)] = omit_value  # ~ inverts the boolean mask
    return img


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the NIfTI image
    nii = nib.load(args.input)
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

    # Modify label IDs based on selected option
    if args.retain_IDs:
        new_img_array = retain_labels(img, args.label_IDs, args.value)
    else:
        new_img_array = set_labels(img, args.label_IDs, args.value)

    # Binarize the image if specified
    if args.binarize:
        new_img_array[new_img_array > 0] = 1

    # Save the modified image as a NIfTI file
    nib.save(nib.Nifti1Image(new_img_array, nii.affine, nii.header), args.output)

    verbose_end_msg()


if __name__ == '__main__':
    main()
