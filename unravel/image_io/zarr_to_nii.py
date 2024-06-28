#!/usr/bin/env python3

"""
Use ``io_zarr_to_nii`` from UNRAVEL to convert an image.zarr to an image.nii.gz.

Usage:
------
    io_zarr_to_nii -i path/img.zarr -o path/img.nii.gz

Notes:
    - Outputs RAS orientation
    - Scaling not preserved
"""

import argparse
import nibabel as nib
import numpy as np
import zarr
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image.zarr', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/image.nii.gz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def zarr_to_ndarray(img_path):
    zarr_dataset = zarr.open(img_path, mode='r')
    return np.array(zarr_dataset)

def define_zarr_to_nii_output(output_path):
    if args.output:
        return args.output
    else:
        return str(args.input).replace(".zarr", ".nii.gz")

@print_func_name_args_times()
def save_as_nii(ndarray, output_path):
    affine = np.eye(4)
    nifti_image = nib.Nifti1Image(ndarray, affine)
    nib.save(nifti_image, output_path)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img = zarr_to_ndarray(args.input)
    output_path = define_zarr_to_nii_output(args.output)
    save_as_nii(img, output_path)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()