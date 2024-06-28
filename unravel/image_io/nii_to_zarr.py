#!/usr/bin/env python3

"""
Use ``io_nii_to_zarr`` from UNRAVEL to convert an image.nii.gz to an image.zarr

Usage:
------
    io_nii_to_zarr -i path/img.nii.gz -o path/img.zarr
"""

import argparse
import dask.array as da
import nibabel as nib
import numpy as np
import zarr
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/image.zarr', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def nii_to_ndarray(img_path):
    nii_img = nib.load(img_path)   
    ndarray = np.asanyarray(nii_img.dataobj) # Preserves dtype
    d_type = ndarray.dtype
    return ndarray, d_type

@print_func_name_args_times()
def save_as_zarr(ndarray, output_path):
    dask_array = da.from_array(ndarray, chunks='auto')
    compressor = zarr.Blosc(cname='lz4', clevel=9, shuffle=zarr.Blosc.BITSHUFFLE)
    dask_array.to_zarr(output_path, compressor=compressor, overwrite=True)

@print_func_name_args_times()
def save_as_zarr(ndarray, output_path, d_type):
    ndarray = ndarray.astype(d_type)
    dask_array = da.from_array(ndarray, chunks='auto')
    compressor = zarr.Blosc(cname='lz4', clevel=9, shuffle=zarr.Blosc.BITSHUFFLE)
    dask_array.to_zarr(output_path, compressor=compressor, overwrite=True)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img, d_type = nii_to_ndarray(args.input)

    if args.output:
        output_path = args.output
    else:
        output_path = str(args.input).replace(".nii.gz", ".zarr")

    save_as_zarr(img, output_path, d_type)

    verbose_end_msg()


if __name__ == '__main__':
    main()